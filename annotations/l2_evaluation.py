"""Deterministic human-reference metrics. No ML runtime, fitting or database access."""
from collections import Counter, defaultdict
import math
import random

METRIC_VERSION = 'l2-human-evaluation-v2'
CI_SEED = 20261013
BOOTSTRAPS = 1000
BINARY = ('gbv', 'not_gbv')


def ratio(a, b):
    return a / b if b else None


def wilson(successes, n):
    if not n:
        return None
    z = 1.959963984540054
    p = successes / n; d = 1 + z*z/n
    center = (p + z*z/(2*n)) / d
    half = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / d
    return [max(0, center-half), min(1, center+half)]


def metric(a, b, *, binomial=False, reason='Zero denominator.'):
    return dict(value=ratio(a, b), numerator=a, denominator=b,
        undefined_reason=None if b else reason,
        ci95=wilson(a, b) if binomial else None,
        ci_method='Wilson score, 95%' if binomial and b else None)


def category(row):
    h, m = row['human_label'], row['model_label']
    if h not in BINARY:
        return 'Human Uncertainty'
    if m == 'borderline':
        return 'Model Abstention'
    return 'TP' if h == m == 'gbv' else 'TN' if h == m == 'not_gbv' else 'FP' if m == 'gbv' else 'FN'


def classification(rows):
    matrix = Counter(TP=0, FP=0, TN=0, FN=0)
    matrix.update(category(r) for r in rows if r['human_label'] in BINARY and r['model_label'] in BINARY)
    tp, fp, tn, fn = (matrix[x] for x in ('TP', 'FP', 'TN', 'FN'))
    n = tp+fp+tn+fn
    classes = {}
    for name, correct, wrong, missed in [('gbv', tp, fp, fn), ('not_gbv', tn, fn, fp)]:
        support = correct + missed
        classes[name] = dict(support=support, predicted_support=correct+wrong,
            precision=metric(correct, correct+wrong if support else 0, reason='No class support or no predictions.'),
            recall=metric(correct, support, binomial=True, reason='No human class support.'),
            f1=metric(2*correct, 2*correct+wrong+missed if support else 0, reason='No human class support.'))
    aggregates = {}
    for aggregation in ('macro', 'weighted'):
        aggregates[aggregation] = {}
        for key in ('precision', 'recall', 'f1'):
            active = list(classes.values()) if aggregation == 'macro' else [v for v in classes.values() if v['support']]
            denom = len(active) if aggregation == 'macro' else n
            values = [v[key]['value'] for v in active]
            defined = bool(denom and all(v is not None for v in values))
            numerator = sum(v[key]['value'] * (1 if aggregation == 'macro' else v['support']) for v in active) if defined else 0
            aggregates[aggregation][key] = metric(numerator, denom if defined else 0, reason='Required class metric is undefined.')
            aggregates[aggregation][key]['support'] = n
    aggregates['micro'] = {k: metric(tp+tn, n) for k in ('precision', 'recall', 'f1')}
    overall = dict(accuracy=metric(tp+tn, n, binomial=True),
        precision=classes['gbv']['precision'], recall=classes['gbv']['recall'], f1=classes['gbv']['f1'],
        macro_f1=aggregates['macro']['f1'], balanced_accuracy=aggregates['macro']['recall'],
        specificity=classes['not_gbv']['recall'], false_positive_rate=metric(fp, fp+tn, binomial=True),
        false_negative_rate=metric(fn, tp+fn, binomial=True), negative_predictive_value=classes['not_gbv']['precision'])
    return dict(confusion_matrix=dict(matrix), binary_evaluable=n, classes=classes, aggregates=aggregates, metric_details=overall)


def probability_analysis(rows):
    cohort = [r for r in rows if r['human_label'] in BINARY]
    n = len(cohort); positives = sum(r['human_label'] == 'gbv' for r in cohort); negatives = n-positives
    roc = []; pr = []; ap = auc = None
    if positives and negatives:
        groups = defaultdict(lambda: [0, 0])
        for r in cohort:
            groups[r['gbv_probability']][0 if r['human_label'] == 'gbv' else 1] += 1
        tp = fp = 0; roc = [[0., 0.]]; pr = [[0., 1.]]; ap = auc = 0.
        previous_recall = previous_fpr = previous_tpr = 0.
        for p in sorted(groups, reverse=True):
            a, b = groups[p]; tp += a; fp += b
            recall, fpr, precision = tp/positives, fp/negatives, tp/(tp+fp)
            auc += (fpr-previous_fpr)*(recall+previous_tpr)/2
            ap += (recall-previous_recall)*precision
            roc.append([fpr, recall]); pr.append([recall, precision])
            previous_recall, previous_fpr, previous_tpr = recall, fpr, recall
    bins = [dict(lower=i/10, upper=(i+1)/10, n=0, sum_probability=0., positives=0) for i in range(10)]
    histogram = {h: [0]*10 for h in BINARY}; brier = loss = 0.
    for r in cohort:
        p = r['gbv_probability']; y = int(r['human_label'] == 'gbv')
        b = bins[min(9, int(p*10))]; b['n'] += 1; b['sum_probability'] += p; b['positives'] += y
        histogram[r['human_label']][min(9, int(p*10))] += 1
        brier += (p-y)**2
        clipped = min(1-1e-15, max(1e-15, p))
        loss -= y*math.log(clipped)+(1-y)*math.log(1-clipped)
    for b in bins:
        b['mean_probability'] = ratio(b.pop('sum_probability'), b['n'])
        b['observed_fraction'] = ratio(b['positives'], b['n'])
    ece = sum(b['n']*abs(b['mean_probability']-b['observed_fraction']) for b in bins if b['n'])
    return dict(support=n, positive_support=positives, negative_support=negatives,
        support_warning='Small class support: probability analyses are descriptive and unstable.' if min(positives,negatives)<10 else None,
        positive_prevalence=metric(positives, n, binomial=True), roc_auc=auc,
        average_precision=ap, auc_undefined_reason=None if positives and negatives else 'Both human binary classes are required.',
        roc_curve=roc, pr_curve=pr, brier_score=metric(brier, n), log_loss=metric(loss, n),
        expected_calibration_error=metric(ece, n), calibration_bins=bins, probability_histogram=histogram,
        definition='All resolved binary human references, including model abstentions. AP = sum(delta recall × precision) at distinct descending scores; ROC uses trapezoids with tied scores grouped. Log loss clips at 1e-15. ECE uses 10 equal-width bins [lower, upper), last bin includes 1. Uncalibrated stored softmax outputs; descriptive calibration only.')


def thresholds(rows, purpose):
    if purpose != 'development_validation':
        return dict(enabled=False, reason='Threshold exploration is restricted to development validation.', points=[])
    points = []
    cohort = [r for r in rows if r['human_label'] in BINARY]
    for positive in (.5, .6, .7, .8, .85, .9, .95):
        negative = round(1-positive, 10)
        changed = [dict(r, model_label='gbv' if r['gbv_probability'] >= positive else
            'not_gbv' if r['gbv_probability'] <= negative else 'borderline') for r in cohort]
        report = classification(changed); n = report['binary_evaluable']; m = report['confusion_matrix']
        positive_total = sum(r['human_label'] == 'gbv' for r in cohort)
        points.append(dict(positive_threshold=positive, negative_threshold=negative,
            resolved_support=len(cohort), human_gbv_support=positive_total,
            predicted_gbv_support=m['TP']+m['FP'], non_abstaining_gbv_support=m['TP']+m['FN'],
            coverage=ratio(n, len(cohort)), abstention_rate=ratio(len(cohort)-n, len(cohort)),
            gbv_precision=report['metric_details']['precision']['value'],
            conditional_gbv_recall=report['metric_details']['recall']['value'],
            gbv_detection_rate=ratio(m['TP'], positive_total),
            false_positives=m['FP'], false_negatives=m['FN'], binary_evaluable=n,
            selective_risk=ratio(m['FP']+m['FN'], n)))
    return dict(enabled=True, points=points,
        definition='Exploratory development analysis — not a final-test result. Selective risk = (FP+FN)/non-abstaining binary support. GBV detection rate = TP/all resolved human GBV, including abstentions. Conditional recall excludes abstentions. Original stored decisions remain the official metrics; no threshold is fitted or persisted.')


def bootstrap_intervals(report):
    """IID percentile bootstrap; withhold small class support, disclose unavailable clusters."""
    classes = report['classes']; n = report['binary_evaluable']
    result = dict(method='IID percentile bootstrap, 95%', seed=CI_SEED, resamples=BOOTSTRAPS,
        support=n, minimum_class_support=10,
        limitation='Article-level IID assumption; related incidents/syndication are not clustered. Intervals do not capture label or sampling bias.')
    if any(v['support'] < 10 for v in classes.values()):
        return dict(result, f1=None, macro_f1=None, reason='At least 10 evaluable references per class are required for these descriptive intervals.')
    population = [k for k, count in report['confusion_matrix'].items() for _ in range(count)]
    rng = random.Random(CI_SEED); scores = defaultdict(list)
    for _ in range(BOOTSTRAPS):
        c = Counter(rng.choices(population, k=n)); tp, fp, tn, fn = (c[k] for k in ('TP', 'FP', 'TN', 'FN'))
        a, b = ratio(2*tp, 2*tp+fp+fn), ratio(2*tn, 2*tn+fp+fn)
        if a is not None and tp+fn: scores['f1'].append(a)
        if a is not None and b is not None and tp+fn and tn+fp: scores['macro_f1'].append((a+b)/2)
    for key in ('f1', 'macro_f1'):
        values = sorted(scores[key]); result[key] = [values[int(.025*(len(values)-1))], values[int(.975*(len(values)-1))]] if len(values) >= .95*BOOTSTRAPS else None
    return result


def language_group(value):
    raw = (value or '').lower().strip()
    if raw in ('en', 'en-ke', 'en-us', 'english'): return 'English'
    if raw in ('sw', 'sw-ke', 'swahili', 'kiswahili'): return 'Swahili'
    if raw in ('sheng',): return 'Sheng'
    if raw in ('code-switched', 'code_switched', 'mixed', 'en-sw', 'sw-en'): return 'Code-switched'
    return 'Unknown'


def subgroup_report(rows, key):
    groups = defaultdict(list)
    for r in rows:
        groups[language_group(r.get('language')) if key == 'language' else r.get(key) or 'unknown'].append(r)
    result = {}
    for name, cohort in sorted(groups.items()):
        report = classification(cohort)
        human = Counter(r['human_label'] for r in cohort); model = Counter(r['model_label'] for r in cohort)
        result[name] = dict(report, sample_size=len(cohort), human_gbv=human['gbv'], human_not_gbv=human['not_gbv'],
            model_gbv=model['gbv'], model_not_gbv=model['not_gbv'], abstentions=model['borderline'],
            warning='Small or missing class support; descriptive only, no ranking.' if len(cohort)<30 or any(v['support']<10 for v in report['classes'].values()) else
                'Unverified metadata and cohort sampling; differences do not establish fairness disparities.')
    return result


def extend_report(report, pairs):
    """Called only after existing accepted-reference and membership validation."""
    resolved = [r for r in pairs if r['human_label'] in BINARY]
    abstentions = [r for r in resolved if r['model_label'] == 'borderline']
    classification_report = classification(pairs)
    report.update(metric_definition_version=METRIC_VERSION, classification=classification_report,
        resolved_binary=len(resolved), human_uncertainty_exclusions=len(pairs)-len(resolved),
        binary_coverage=metric(classification_report['binary_evaluable'], len(resolved), binomial=True),
        abstention_all=metric(sum(r['model_label']=='borderline' for r in pairs), len(pairs), binomial=True),
        abstention_resolved=metric(len(abstentions), len(resolved), binomial=True),
        abstained_human_gbv=sum(r['human_label']=='gbv' for r in abstentions),
        abstained_human_not_gbv=sum(r['human_label']=='not_gbv' for r in abstentions))
    if report['purpose'] == 'diagnostic':
        # Preserve original diagnostic/enrichment prohibition for every added metric.
        report.update(classification=None, probability=None, subgroups=None, uncertainty=None,
                      threshold_analysis=thresholds([], 'diagnostic'), binary_coverage=None)
        return report
    probability = probability_analysis(pairs)
    report.update(probability=probability, roc_auc=probability['roc_auc'], pr_auc=probability['average_precision'],
        calibration=probability['calibration_bins'], threshold_analysis=thresholds(pairs, report['purpose']),
        subgroups={k: subgroup_report(pairs, k) for k in ('source', 'language')},
        uncertainty=bootstrap_intervals(classification_report))
    report['metrics'].update({k:classification_report['metric_details'][k]['value'] for k in ('accuracy','precision','recall','f1')})
    return report
