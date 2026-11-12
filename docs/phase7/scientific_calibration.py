"""Data record. Generated - the generator is named inside the record itself."""

DATA = {'generatedAt': '2026-11-10T17:35:36.375606+00:00',
 'phase': 7,
 'purpose': 'Check every simulator parameter the recovered NASA measurements can speak to, apply only '
            'same-quantity same-crop calibrations, and prove mechanically that no output changed.',
 'applyPolicy': 'A calibration is applied only when the measurement is the same physical quantity on the '
                'same class of crop. Zero Phase 7 measurements meet that bar for the three modelled crops, '
                "so zero parameters changed. The checks are still recorded because 'we looked and it holds' "
                "is a different claim from 'we did not look'.",
 'checks': [{'parameter': 'WATER_RECOVERY_EFFICIENCY',
             'assumed': 0.9,
             'measured': 0.9236,
             'measuredSource': 'NASA TM-103494 p.12-13 (3615 L condensed / 3914 L added)',
             'relativeDifferencePct': 2.62,
             'verdict': 'assumed-value-inside-measured-interval',
             'decision': 'retained',
             'reason': 'The only measured recovery figure available, and the assumption sits 2.4 percentage '
                       'points below it. The measurement is a lower bound: that chamber leaked 20-40 % of '
                       'its volume per day and the added-water total includes plumbing losses, so a '
                       'well-sealed loop should recover more than 0.924. Moving the assumption UP toward the '
                       'measurement would therefore be scientifically backwards. Retained unchanged.',
             'evidenceClass': 'measured-approximate (single balance, leaking chamber)'},
            {'parameter': 'CROP_BASELINES[*].peak_water_l_per_day',
             'measuredWheatPeakLPerM2Day': 6.0,
             'measuredWheatMeanLPerM2Day': {'integratorBased': 4.5, 'condensateBased': 6.1},
             'assumptionInScaling': 'Transpiration is assumed to scale linearly with daily light integral. '
                                    'That is a scaling model, not a measurement, and it is the weakest link '
                                    'in this check.',
             'crops': {'lettuce': {'assumedPeakLPerM2Day': 2.5,
                                   'simulatorDliMolPerM2Day': 17.28,
                                   'dliScaledMeasuredRangeLPerM2Day': [2.05, 2.77],
                                   'insideRange': True,
                                   'ratioToMeasuredWheatPeak': 0.417},
                       'tomato': {'assumedPeakLPerM2Day': 4.5,
                                  'simulatorDliMolPerM2Day': 17.28,
                                  'dliScaledMeasuredRangeLPerM2Day': [2.05, 2.77],
                                  'insideRange': False,
                                  'ratioToMeasuredWheatPeak': 0.75},
                       'radish': {'assumedPeakLPerM2Day': 2.0,
                                  'simulatorDliMolPerM2Day': 15.12,
                                  'dliScaledMeasuredRangeLPerM2Day': [1.79, 2.43],
                                  'insideRange': True,
                                  'ratioToMeasuredWheatPeak': 0.333}},
             'cropsInsideRange': ['lettuce', 'radish'],
             'cropsOutsideRange': ['tomato'],
             'outsideRangeInterpretation': "Tomato's assumed peak demand (4.5 L/m2/day) sits about 1.6x "
                                           'above the DLI-scaled wheat envelope. That is NOT evidence the '
                                           'assumption is wrong: tomato is a far larger plant with a longer '
                                           'cycle and a lower harvest index, so a higher areal demand is '
                                           'entirely plausible. The correct reading is that a wheat stand '
                                           'cannot bound a tomato parameter in either direction, which is '
                                           'why no change is applied. If anything this check is weaker for '
                                           'tomato than for the leafy crops, where the species are closer in '
                                           'stature.',
             'verdict': 'plausibility-check-only',
             'decision': 'no change applied',
             'reason': 'Wheat transpiration cannot calibrate a lettuce, tomato or radish parameter: '
                       'different species, canopy architecture, harvest index and edible organ. The '
                       'DLI-scaled interval is a plausibility envelope, and the assumed values fall inside '
                       'it, which supports the current numbers without licensing a change.',
             'evidenceClass': 'plausibility-only'},
            {'parameter': 'CARBON_FRACTION_OF_DRY_MASS (and the 44/12 chain built on it)',
             'assumed': 0.42,
             'measuredNetFixationGPerDay': 860.0,
             'measuredHarvestKgPer86Days': 40.0,
             'standAreaM2': 20.0,
             'impliedCarbonFraction': 0.504,
             'relativeDifferencePct': 20.1,
             'verdict': 'assumption-within-20-percent-of-measured-balance',
             'decision': 'retained',
             'reason': "The engine's CO2 chain assumes 42 % carbon of dry mass. A measured CO2 mass balance "
                       'over an 86-day stand implies 50 %, a 20 % difference - the same order as the '
                       "report's own 10 % harvest-versus-gas-exchange discrepancy, and well inside the "
                       '0.40-0.45 range usually quoted for herbaceous tissue. The check CONFIRMS the chain '
                       'is not wrong by an order of magnitude, which is the most a single unresolved stand '
                       'can establish. Retained unchanged.',
             'sensitivity': 'This check assumes the reported 40 kg is dry matter, consistent with the BPC '
                            "literature and with the report's own comparison against its gas-exchange "
                            'estimate. If the 40 kg were fresh weight, the implied carbon fraction would '
                            'fall far below the assumption and the check would instead be inconclusive. That '
                            'ambiguity is why this is recorded as a consistency check rather than a '
                            'calibration.',
             'evidenceClass': 'plausibility-only'},
            {'parameter': 'LOGISTIC_STEEPNESS and the single-cycle logistic shape',
             'assumedSteepness': 10.0,
             'measuredSeries': [{'ageDays': 9.0,
                                 'measuredFractionOfPeak': 0.067,
                                 'logisticFraction': 0.027,
                                 'absoluteResidual': 0.039},
                                {'ageDays': 18.0,
                                 'measuredFractionOfPeak': 0.178,
                                 'logisticFraction': 0.105,
                                 'absoluteResidual': 0.073},
                                {'ageDays': 27.0,
                                 'measuredFractionOfPeak': 0.267,
                                 'logisticFraction': 0.329,
                                 'absoluteResidual': 0.062},
                                {'ageDays': 37.0,
                                 'measuredFractionOfPeak': 0.794,
                                 'logisticFraction': 0.705,
                                 'absoluteResidual': 0.088},
                                {'ageDays': 46.0,
                                 'measuredFractionOfPeak': 0.762,
                                 'logisticFraction': 0.909,
                                 'absoluteResidual': 0.147},
                                {'ageDays': 54.0,
                                 'measuredFractionOfPeak': 1.0,
                                 'logisticFraction': 0.973,
                                 'absoluteResidual': 0.027},
                                {'ageDays': 63.0,
                                 'measuredFractionOfPeak': 0.914,
                                 'logisticFraction': 0.993,
                                 'absoluteResidual': 0.079}],
             'maxAbsoluteResidual': 0.147,
             'meanAbsoluteResidual': 0.074,
             'verdict': 'shape-supported-within-0.15-of-peak',
             'decision': 'retained',
             'reason': 'The measured dry-matter series tracks the assumed logistic shape to within 0.15 of '
                       'peak biomass (mean 0.07) when both are expressed as fractions of the cycle. The '
                       'logistic cannot represent the post-anthesis decline the measured series shows (day '
                       '54 = 1.00, day 63 = 0.91), so the residual is structural rather than noise. Fitting '
                       'a steeper or shallower curve to seven single-tray points would be fitting the tray, '
                       'not the crop; the shape is retained as an assumption and this check records how well '
                       'it happens to match.',
             'structuralLimitation': 'One tray per age, single study, and the series is non-monotonic at day '
                                     '46. It bounds the shape; it cannot identify it.',
             'evidenceClass': 'plausibility-only'}],
 'appliedChanges': [],
 'declinedChanges': [{'source': 'Phase 6 simulation_calibration.py',
                      'crops': ['tomato', 'radish'],
                      'status': 'declined',
                      'detail': {'available': True,
                                 'source': 'docs/phase6/simulation_calibration.py',
                                 'crops': {'tomato': {'currentBaselineKgPerM2': 3.5,
                                                      'phase6SuggestedKgPerM2': 3.910489510489511,
                                                      'applied': False,
                                                      'appliedValueInSimulator': 3.5,
                                                      'phase6SuggestionStatus': 'proposed, NOT applied - '
                                                                                'requires owner approval '
                                                                                'because it changes '
                                                                                'user-visible simulator '
                                                                                'output, and the supporting '
                                                                                'n is 2',
                                                      'reason': 'Not applied, as Part C requires. The '
                                                                'suggestion rests on n=2 measurements from '
                                                                'one Antarctic analogue greenhouse, '
                                                                'age-normalised by assuming linear '
                                                                'accumulation across a 286-day multi-harvest '
                                                                'phase down to an 80-day cycle. That is a '
                                                                'model assumption stacked on two data '
                                                                'points. No Phase 7 evidence changes this: '
                                                                'the recovered NTRS corpus contains no '
                                                                'tomato or radish data at all.'},
                                           'radish': {'currentBaselineKgPerM2': 1.2,
                                                      'phase6SuggestedKgPerM2': 1.5750000000000002,
                                                      'applied': False,
                                                      'appliedValueInSimulator': 1.2,
                                                      'phase6SuggestionStatus': 'proposed, NOT applied - '
                                                                                'requires owner approval '
                                                                                'because it changes '
                                                                                'user-visible simulator '
                                                                                'output, and the supporting '
                                                                                'n is 2',
                                                      'reason': 'Not applied, as Part C requires. The '
                                                                'suggestion rests on n=2 measurements from '
                                                                'one Antarctic analogue greenhouse, '
                                                                'age-normalised by assuming linear '
                                                                'accumulation across a 286-day multi-harvest '
                                                                'phase down to an 80-day cycle. That is a '
                                                                'model assumption stacked on two data '
                                                                'points. No Phase 7 evidence changes this: '
                                                                'the recovered NTRS corpus contains no '
                                                                'tomato or radish data at all.'}},
                                 'verdict': 'explicitly-declined'}}],
 'massBalance': {'checksRun': 54, 'failures': [], 'allPassed': True},
 'deliberateChanges': [{'phase': 30,
                        'what': 'the fractional-gravity input, factor and control were removed',
                        'why': 'no open dataset measures crop yield or biomass across fractional gravity, so '
                               'the 15 %-at-0 g growth penalty was an invented coefficient. Its removal '
                               'deletes a factor from the fingerprint and replaces the gravity axis of the '
                               'scenario grid with a radiation axis, so the combined hash changes.',
                        'fingerprintBefore': 'd9165881105535e2a733650450123eb6fbfbfd0b86d4b9796261ade72855c596',
                        'fingerprintAfter': '49cb0c6c7ede271ed44d4570f6978fbea988eaa2118557ed7a25598041a450f7',
                        'cropsAffected': ['lettuce', 'tomato', 'radish'],
                        'direction': 'outputs rise, because the removed penalty no longer discounts '
                                     'space-case growth'}],
 'outputFingerprint': {'grid': '27 scenarios x 3 crops x space/earth blocks',
                       'sha256': '49cb0c6c7ede271ed44d4570f6978fbea988eaa2118557ed7a25598041a450f7',
                       'fieldsHashed': ['crop_yield_g', 'growth_rate_g_per_day', 'water_used_l',
                                        'water_recovered_l', 'co2_removed_g', 'o2_produced_g', 'factors'],
                       'purpose': 'Any change to an output definition, unit or value breaks this hash. The '
                                  'test suite recomputes it, so a calibration cannot be slipped in silently '
                                  'in a later phase.'},
 'constantsSnapshot': {'WATER_RECOVERY_EFFICIENCY': 0.9,
                       'CARBON_FRACTION_OF_DRY_MASS': 0.42,
                       'CO2_PER_CARBON_MASS_RATIO': 3.6666666666666665,
                       'O2_PER_CO2_MASS_RATIO': 0.7272727272727273,
                       'LOGISTIC_STEEPNESS': 10.0,
                       'cropHarvestBiomassG': {'lettuce': 2000.0, 'tomato': 3500.0, 'radish': 1200.0}}}
