import os
import warnings
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    classification_report,
    confusion_matrix,
)

warnings.filterwarnings('ignore')

INPUT_CSV  = "grid_search_results.csv"
OUTPUT_DIR = "wyniki_magisterka"
PLOTS_DIR  = os.path.join(OUTPUT_DIR, "wykresy")
TABLES_DIR = os.path.join(OUTPUT_DIR, "tabele")

VALID_CATEGORIES      = ["rec.autos", "sci.space", "comp.graphics", "misc.forsale", "sci.med"]
ALL_LABELS_WITH_ERROR = VALID_CATEGORIES + ["inne_blad"]
COT_PROMPTS           = {"P4_ChainOfThought", "P6_FewShot_CoT"}

os.makedirs(PLOTS_DIR,  exist_ok=True)
os.makedirs(TABLES_DIR, exist_ok=True)

sns.set_theme(style="whitegrid", context="paper", font_scale=1.2)
plt.rcParams.update({
    'figure.dpi':   300,
    'savefig.dpi':  300,
    'savefig.bbox': 'tight',
    'font.size':    11
})


def clean_predictions(df):
    df = df.copy()
    df['predicted_label'] = df['predicted_label'].astype(str)

    def extract_label(row):
        text        = str(row['predicted_label']).lower()
        prompt_type = row['prompt_type']

        if prompt_type in COT_PROMPTS:
            for line in reversed(text.splitlines()):
                line = line.strip()
                if "wynik:" in line:
                    candidate = line.split("wynik:")[-1].strip().lower()
                    for label in VALID_CATEGORIES:
                        if label in candidate:
                            return label

        for label in VALID_CATEGORIES:
            if label in text:
                return label

        return "inne_blad"

    df['predicted_clean'] = df.apply(extract_label, axis=1)
    return df


def classify_family(model_name):
    m = str(model_name).lower()
    if "phi"   in m: return "Phi"
    if "llama" in m: return "Llama"
    if "gemma" in m: return "Gemma"
    return "Inne"


def classify_type(model_name):
    return "Douczony (Tuned)" if "tuned" in str(model_name).lower() else "Bazowy (Base)"


def safe_filename(text):
    return str(text).replace(':', '_').replace('/', '_').replace(' ', '_')



def generate_master_thesis_analysis():
    print(f"Wczytywanie danych z pliku: {INPUT_CSV}")
    try:
        df = pd.read_csv(INPUT_CSV, sep=',', engine='python')
        df.columns = [c.strip().replace(';', '') for c in df.columns]
        df = df.apply(lambda col: col.map(lambda x: str(x).rstrip(';').strip()) if col.dtype == object else col)
    except FileNotFoundError:
        return

    df = clean_predictions(df)
    df['Rodzina'] = df['model'].apply(classify_family)
    df['Typ']     = df['model'].apply(classify_type)

    class_dist = (
        df[['email_id', 'true_label']].drop_duplicates()['true_label']
        .value_counts().reset_index()
    )
    class_dist.columns = ['Klasa', 'Liczba_prob']
    class_dist['Udzial_proc'] = (
        class_dist['Liczba_prob'] / class_dist['Liczba_prob'].sum() * 100
    ).round(2)
    class_dist.to_csv(os.path.join(TABLES_DIR, 'tabela_1_rozklad_klas.csv'), index=False)

    metrics     = []
    reports_all = []

    for (model, prompt), group in df.groupby(['model', 'prompt_type']):
        y_true = group['true_label']
        y_pred = group['predicted_clean']

        metrics.append({
            'Model':              model,
            'Prompt':             prompt,
            'Accuracy':           accuracy_score(y_true, y_pred),
            'Precision_Macro':    precision_score(y_true, y_pred, average='macro',    zero_division=0),
            'Recall_Macro':       recall_score(   y_true, y_pred, average='macro',    zero_division=0),
            'F1_Macro':           f1_score(       y_true, y_pred, average='macro',    zero_division=0),
            'F1_Weighted':        f1_score(       y_true, y_pred, average='weighted', zero_division=0),
            'Hallucination_Rate': (y_pred == 'inne_blad').mean(),
            'Rodzina':            classify_family(model),
            'Typ':                classify_type(model),
        })

        report = classification_report(
            y_true, y_pred,
            labels=VALID_CATEGORIES + ['inne_blad'],
            output_dict=True,
            zero_division=0
        )
        for label, values in report.items():
            if isinstance(values, dict):
                reports_all.append({
                    'Model':     model,
                    'Prompt':    prompt,
                    'Label':     label,
                    'Precision': values.get('precision', 0),
                    'Recall':    values.get('recall',    0),
                    'F1_Score':  values.get('f1-score',  0),
                    'Support':   values.get('support',   0),
                })

    metrics_df = pd.DataFrame(metrics).sort_values(by='F1_Macro', ascending=False).reset_index(drop=True)
    reports_df = pd.DataFrame(reports_all)

    metrics_df.to_csv(os.path.join(TABLES_DIR, 'tabela_2_metryki_glowne.csv'),    index=False)
    reports_df.to_csv(os.path.join(TABLES_DIR, 'tabela_3_metryki_per_klasa.csv'), index=False)

    avg_by_family_type = (
        metrics_df.groupby(['Rodzina', 'Typ'])
        [['Accuracy', 'F1_Macro', 'F1_Weighted', 'Hallucination_Rate']]
        .mean().reset_index()
    )
    avg_by_family_type.to_csv(os.path.join(TABLES_DIR, 'tabela_4_srednie_bazowy_vs_tuned.csv'), index=False)

    delta_rows = []
    for family in avg_by_family_type['Rodzina'].unique():
        fam   = avg_by_family_type[avg_by_family_type['Rodzina'] == family]
        base  = fam[fam['Typ'] == 'Bazowy (Base)']
        tuned = fam[fam['Typ'] == 'Douczony (Tuned)']
        if not base.empty and not tuned.empty:
            delta_rows.append({
                'Rodzina':             family,
                'Delta_Accuracy':      round(float(tuned['Accuracy'].iloc[0])          - float(base['Accuracy'].iloc[0]),          4),
                'Delta_F1_Macro':      round(float(tuned['F1_Macro'].iloc[0])           - float(base['F1_Macro'].iloc[0]),           4),
                'Delta_F1_Weighted':   round(float(tuned['F1_Weighted'].iloc[0])        - float(base['F1_Weighted'].iloc[0]),        4),
                'Delta_Hallucination': round(float(tuned['Hallucination_Rate'].iloc[0]) - float(base['Hallucination_Rate'].iloc[0]), 4),
            })
    pd.DataFrame(delta_rows).to_csv(os.path.join(TABLES_DIR, 'tabela_5_delta_tuned_vs_base.csv'), index=False)

    ranking_df = metrics_df.copy()
    ranking_df.insert(0, 'Ranking', range(1, len(ranking_df) + 1))
    ranking_df.to_csv(os.path.join(TABLES_DIR, 'tabela_6_ranking_koncowy.csv'), index=False)

    plt.figure(figsize=(14, 8))
    pivot_f1 = metrics_df.pivot(index='Model', columns='Prompt', values='F1_Macro')
    sns.heatmap(pivot_f1, annot=True, fmt='.3f', cmap='YlGnBu', linewidths=.5)
    plt.title('Heatmapa F1-Macro: Modele vs Prompty')
    plt.xlabel('Typ promptu')
    plt.ylabel('Model')
    plt.savefig(os.path.join(PLOTS_DIR, 'wykres_1_heatmapa_f1_macro.png'))
    plt.close()

    plt.figure(figsize=(14, 8))
    pivot_acc = metrics_df.pivot(index='Model', columns='Prompt', values='Accuracy')
    sns.heatmap(pivot_acc, annot=True, fmt='.3f', cmap='magma', linewidths=.5)
    plt.title('Heatmapa Accuracy: Modele vs Prompty')
    plt.xlabel('Typ promptu')
    plt.ylabel('Model')
    plt.savefig(os.path.join(PLOTS_DIR, 'wykres_2_heatmapa_accuracy.png'))
    plt.close()

    plt.figure(figsize=(14, 7))
    sns.barplot(data=metrics_df, x='Model', y='F1_Macro', hue='Prompt', palette='Set2')
    plt.title('F1-Macro dla wszystkich modeli i wariantów promptów')
    plt.xticks(rotation=45)
    plt.ylim(0, 1.05)
    plt.legend(title='Prompt', bbox_to_anchor=(1.02, 1), loc='upper left')
    plt.savefig(os.path.join(PLOTS_DIR, 'wykres_3_barplot_f1_konfiguracje.png'))
    plt.close()

    plt.figure(figsize=(10, 6))
    sns.barplot(data=avg_by_family_type, x='Rodzina', y='F1_Macro', hue='Typ',
                palette=['#d95f02', '#1b9e77'])
    plt.title('Wpływ fine-tuningu na F1-Macro\n(średnia po wszystkich wariantach promptów)')
    plt.ylabel('Średni F1-Macro')
    plt.ylim(0, 1.05)
    plt.legend(title='Wersja modelu')
    plt.savefig(os.path.join(PLOTS_DIR, 'wykres_4_wplyw_finetuningu.png'))
    plt.close()

    plt.figure(figsize=(12, 6))
    sns.pointplot(data=metrics_df, x='Prompt', y='F1_Macro', hue='Rodzina')
    plt.title('Wrażliwość architektur modeli na zmiany typu promptu')
    plt.ylabel('F1-Macro')
    plt.xlabel('Wariant promptu')
    plt.xticks(rotation=20)
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.legend(title='Rodzina modeli')
    plt.savefig(os.path.join(PLOTS_DIR, 'wykres_5_wplyw_promptow_linie.png'))
    plt.close()

    plt.figure(figsize=(14, 6))
    sns.barplot(data=metrics_df, x='Model', y='Hallucination_Rate', hue='Prompt', palette='rocket')
    plt.title('Odsetek halucynacji (odpowiedzi poza listą kategorii) per konfiguracja')
    plt.ylabel('Hallucination Rate')
    plt.xticks(rotation=45)
    plt.legend(title='Prompt', bbox_to_anchor=(1.02, 1), loc='upper left')
    plt.savefig(os.path.join(PLOTS_DIR, 'wykres_6_halucynacje.png'))
    plt.close()

    plt.figure(figsize=(10, 6))
    sns.scatterplot(data=metrics_df, x='Hallucination_Rate', y='F1_Macro',
                    hue='Rodzina', style='Typ', s=150)
    plt.title('Zależność między odsetkiem halucynacji a F1-Macro')
    plt.xlabel('Hallucination Rate')
    plt.ylabel('F1-Macro')
    plt.legend(title='Model')
    plt.savefig(os.path.join(PLOTS_DIR, 'wykres_7_scatter_f1_vs_halucynacje.png'))
    plt.close()

    plt.figure(figsize=(10, 6))
    sns.boxplot(data=metrics_df, x='Rodzina', y='F1_Macro', hue='Typ', palette='pastel')
    plt.title('Rozkład F1-Macro per rodzina modelu\n(wariancja względem wariantów promptów)')
    plt.ylabel('F1-Macro')
    plt.savefig(os.path.join(PLOTS_DIR, 'wykres_8_boxplot_stabilnosc.png'))
    plt.close()

    best_row    = metrics_df.iloc[0]
    best_model  = best_row['Model']
    best_prompt = best_row['Prompt']
    best_subset = df[(df['model'] == best_model) & (df['prompt_type'] == best_prompt)]

    best_report = classification_report(
        best_subset['true_label'], best_subset['predicted_clean'],
        labels=VALID_CATEGORIES, output_dict=True, zero_division=0
    )
    best_class_rows = [
        {
            'Klasa':     label,
            'Precision': best_report[label]['precision'],
            'Recall':    best_report[label]['recall'],
            'F1_Score':  best_report[label]['f1-score'],
            'Support':   best_report[label]['support'],
        }
        for label in VALID_CATEGORIES
    ]
    best_class_df = pd.DataFrame(best_class_rows)
    best_class_df.to_csv(os.path.join(TABLES_DIR, 'tabela_7_najlepszy_model_per_klasa.csv'), index=False)
    print("✅ Tabela 7: Metryki per klasa najlepszego modelu")

    melted_best = best_class_df.melt(
        id_vars='Klasa',
        value_vars=['Precision', 'Recall', 'F1_Score'],
        var_name='Metryka', value_name='Wartosc'
    )
    plt.figure(figsize=(12, 6))
    sns.barplot(data=melted_best, x='Klasa', y='Wartosc', hue='Metryka')
    plt.title(f'Precision / Recall / F1 per klasa — najlepsza konfiguracja\n{best_model} | {best_prompt}')
    plt.ylim(0, 1.05)
    plt.savefig(os.path.join(PLOTS_DIR, 'wykres_9_metryki_per_klasa_best.png'))
    plt.close()

    worst_row    = metrics_df.iloc[-1]
    worst_model  = worst_row['Model']
    worst_prompt = worst_row['Prompt']

    for model_name, prompt_name, desc, cmap_color in [
        (best_model,  best_prompt,  'zwyciezca',  'Blues'),
        (worst_model, worst_prompt, 'najslabszy', 'Reds'),
    ]:
        subset = df[(df['model'] == model_name) & (df['prompt_type'] == prompt_name)]
        cm = confusion_matrix(
            subset['true_label'], subset['predicted_clean'],
            labels=ALL_LABELS_WITH_ERROR
        )
        plt.figure(figsize=(10, 8))
        sns.heatmap(cm, annot=True, fmt='d', cmap=cmap_color,
                    xticklabels=ALL_LABELS_WITH_ERROR,
                    yticklabels=ALL_LABELS_WITH_ERROR,
                    cbar=False)
        plt.title(f'Macierz błędów — {desc}\n{model_name} | {prompt_name}')
        plt.xlabel('Predykcja modelu')
        plt.ylabel('Etykieta rzeczywista')
        plt.xticks(rotation=45, ha='right')
        plt.yticks(rotation=0)
        plt.savefig(os.path.join(PLOTS_DIR,
            f'wykres_macierz_{desc}_{safe_filename(model_name)}.png'))
        plt.close()

    errors = best_subset[best_subset['true_label'] != best_subset['predicted_clean']]
    if not errors.empty:
        error_counts = (
            errors.groupby(['true_label', 'predicted_clean'])
            .size().reset_index(name='Liczba')
            .sort_values('Liczba', ascending=False)
        )
        error_counts.to_csv(os.path.join(TABLES_DIR, 'tabela_8_najczestsze_pomylki.csv'), index=False)

    plt.figure(figsize=(14, 8))
    pivot_prec = metrics_df.pivot(index='Model', columns='Prompt', values='Precision_Macro')
    sns.heatmap(pivot_prec, annot=True, fmt='.3f', cmap='Blues', linewidths=.5)
    plt.title('Heatmapa Precision-Macro: Modele vs Prompty')
    plt.xlabel('Typ promptu')
    plt.ylabel('Model')
    plt.savefig(os.path.join(PLOTS_DIR, 'wykres_12_heatmapa_precision.png'))
    plt.close()

    plt.figure(figsize=(14, 8))
    pivot_rec = metrics_df.pivot(index='Model', columns='Prompt', values='Recall_Macro')
    sns.heatmap(pivot_rec, annot=True, fmt='.3f', cmap='Greens', linewidths=.5)
    plt.title('Heatmapa Recall-Macro: Modele vs Prompty')
    plt.xlabel('Typ promptu')
    plt.ylabel('Model')
    plt.savefig(os.path.join(PLOTS_DIR, 'wykres_13_heatmapa_recall.png'))
    plt.close()

    plt.figure(figsize=(10, 8))
    sns.scatterplot(data=metrics_df, x='Precision_Macro', y='Recall_Macro',
                    hue='Rodzina', style='Typ', s=200)
    for _, row in metrics_df.iterrows():
        plt.annotate(f"{row['Model']}\n{row['Prompt']}",
                     (row['Precision_Macro'], row['Recall_Macro']),
                     fontsize=7, alpha=0.7,
                     xytext=(5, 5), textcoords='offset points')
    plt.plot([0, 1], [0, 1], 'k--', alpha=0.3, label='Precision = Recall')
    plt.title('Trade-off Precision vs Recall\n(wszystkie konfiguracje modeli i promptów)')
    plt.xlabel('Precision Macro')
    plt.ylabel('Recall Macro')
    plt.xlim(0, 1.05)
    plt.ylim(0, 1.05)
    plt.legend(title='Model')
    plt.savefig(os.path.join(PLOTS_DIR, 'wykres_14_precision_vs_recall.png'))
    plt.close()

    worst_subset = df[(df['model'] == worst_model) & (df['prompt_type'] == worst_prompt)]
    worst_report = classification_report(
        worst_subset['true_label'], worst_subset['predicted_clean'],
        labels=VALID_CATEGORIES, output_dict=True, zero_division=0
    )
    worst_class_rows = [
        {
            'Klasa':     label,
            'Precision': worst_report[label]['precision'],
            'Recall':    worst_report[label]['recall'],
            'F1_Score':  worst_report[label]['f1-score'],
        }
        for label in VALID_CATEGORIES
    ]
    worst_class_df = pd.DataFrame(worst_class_rows)
    worst_class_df.to_csv(os.path.join(TABLES_DIR, 'tabela_9_najgorszy_model_per_klasa.csv'), index=False)

    melted_worst = worst_class_df.melt(
        id_vars='Klasa',
        value_vars=['Precision', 'Recall', 'F1_Score'],
        var_name='Metryka', value_name='Wartosc'
    )
    plt.figure(figsize=(12, 6))
    sns.barplot(data=melted_worst, x='Klasa', y='Wartosc', hue='Metryka')
    plt.title(f'Precision / Recall / F1 per klasa — najsłabsza konfiguracja\n{worst_model} | {worst_prompt}')
    plt.ylim(0, 1.05)
    plt.savefig(os.path.join(PLOTS_DIR, 'wykres_15_metryki_per_klasa_worst.png'))
    plt.close()



if __name__ == '__main__':
    generate_master_thesis_analysis()