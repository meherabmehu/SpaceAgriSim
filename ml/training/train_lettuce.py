"""Earth-only lettuce random forest; nested whole-experiment validation."""
import safedata
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestRegressor
from sklearn.dummy import DummyRegressor
from sklearn.model_selection import GroupKFold, GridSearchCV
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from download_external_lettuce import acquire
from nasa_pipeline import save_json, stamp

def metrics(y,p):
    return {'MAE':float(mean_absolute_error(y,p)),'RMSE':float(np.sqrt(mean_squared_error(y,p))),'R2':float(r2_score(y,p))}

def main():
    source=acquire()
    frame=pd.read_excel(ROOT/'data/raw/WUR-lettuce/original_dataset_lettuce.xlsx',sheet_name='data')
    mapping={'Experiment':'experiment','Plant':'plantId','Days after Transplanting':'daysAfterTransplant','T_air':'airTemperature','T_root':'rootTemperature','PPFD':'ppfd','FW_Shoot':'freshShootMassG'}
    frame=frame[list(mapping)].rename(columns=mapping)
    features=['daysAfterTransplant','airTemperature','rootTemperature','ppfd']
    if frame.isna().any().any() or (frame.freshShootMassG<0).any():
        raise ValueError('Invalid measured endpoints; inspect source instead of imputing targets')
    frame.to_csv(ROOT/'data/processed/lettuce_earth.csv',index=False,lineterminator='\n')
    x=frame[features].to_numpy(); y=frame.freshShootMassG.to_numpy(); groups=frame.experiment.to_numpy()
    prediction=np.zeros(len(y)); baseline=np.zeros(len(y)); splits=[]
    grid={'max_depth':[5,8],'min_samples_leaf':[2,5]}
    outer=GroupKFold(4)
    for fold,(train,test) in enumerate(outer.split(x,y,groups)):
        search=GridSearchCV(RandomForestRegressor(n_estimators=64,random_state=42,n_jobs=1),grid,cv=GroupKFold(3),scoring='neg_mean_absolute_error')
        search.fit(x[train],y[train],groups=groups[train])
        prediction[test]=search.predict(x[test]);baseline[test]=DummyRegressor().fit(x[train],y[train]).predict(x[test])
        splits.append({'fold':fold,'trainExperiments':sorted(set(groups[train])),'testExperiments':sorted(set(groups[test])),'hyperparameters':search.best_params_})
    final=GridSearchCV(RandomForestRegressor(n_estimators=64,random_state=42,n_jobs=1),grid,cv=outer,scoring='neg_mean_absolute_error')
    final.fit(x,y,groups=groups)
    forest=[]
    for estimator in final.best_estimator_.estimators_:
        tree=estimator.tree_
        forest.append({'left':tree.children_left.tolist(),'right':tree.children_right.tolist(),'feature':tree.feature.tolist(),'threshold':tree.threshold.tolist(),'value':tree.value[:,0,0].tolist()})
    residual=np.abs(y-prediction)
    card={'id':'lettuce-earth-growth-v1','name':'Lettuce Earth growth · WUR random forest','version':'1.0.0','status':'trained-exploratory','trainedAt':stamp(),'task':'Earth-only fresh shoot mass regression','sourceStudy':'WUR-lettuce','sourceUrl':source['sourceUrl'],'sourceType':'external scientific data (not NASA)','license':source['license'],'crop':'lettuce','method':'External-scientific-data-trained exploratory regression','samples':len(y),'groups':len(set(groups)),'features':features,'target':'freshShootMassG','unit':'g fresh shoot mass/plant','metrics':metrics(y,prediction),'baselineMetrics':metrics(y,baseline),'validation':'Nested leave-one-experiment-out CV (4 outer folds, 3 inner folds); all plants/treatments from each experiment remain together. Independent-study validation unavailable.','seed':42,'hyperparameters':final.best_params_,'domain':{name:{'min':float(x[:,i].min()),'max':float(x[:,i].max())} for i,name in enumerate(features)},'interval':{'radius':float(np.quantile(residual,.9,method='higher')),'kind':'90th percentile absolute outer-CV residual; uncalibrated descriptive range','nominalCoverage':None},'limitations':source['limitations']+['Only Batavia Othilie lettuce on Earth; not calibrated for partial gravity or radiation.','No inference for water stress, nutrient stress, CO2 response, other cultivars, or different photoperiods.','Measured domain is 2–29 days after transplant, air/root 20–32 C, PPFD 200–750 µmol/m²/s; treatment grid is sparse.','Environmental combinations omitted for tip burn are unsupported even inside marginal ranges.','Fresh shoot mass per plant is not edible harvest per square meter; no planting-density conversion is assumed.'],'forest':forest}
    path=ROOT/'ml/artifacts/lettuce-earth-growth-v1'
    # Compact tree arrays keep this inspectable artifact below 1 MB.
    safedata.dump(card, path)
    register=ROOT/'ml/artifacts/registry'; registry=safedata.load(register)
    registry['models']=[m for m in registry['models'] if m['id']!=card['id']]+[{'id':card['id'],'artifact':'ml/artifacts/'+path.name,'sha256':hashlib.sha256(safedata.bytes(path)).hexdigest()}]
    registry['externalDataVersion']=hashlib.sha256(json.dumps(source['files'],sort_keys=True).encode()).hexdigest()
    registry['externalTrainingEnvironment']={'numpy':np.__version__,'pandas':pd.__version__,'sklearn':sklearn.__version__}
    save_json(register,registry)
    out=frame.copy();out['outerCvPrediction']=prediction;out['baselinePrediction']=baseline
    out.to_csv(ROOT/'ml/evaluation/lettuce_out_of_fold.csv',index=False,lineterminator='\n')
    save_json(ROOT/'ml/evaluation/lettuce_splits',splits)
    print(json.dumps({k:card[k] for k in ['id','samples','groups','metrics','baselineMetrics','hyperparameters']},indent=2))

if __name__=='__main__':main()
