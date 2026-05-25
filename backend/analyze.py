import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import confusion_matrix, classification_report


def analyze_llm_results(csv_path: str):
    df = pd.read_csv(csv_path)

    summary_df = df[df['row_index'] == -1].copy()
    predictions_df = df[df['row_index'] != -1].copy()

    metrics = ['accuracy', 'macro_precision', 'macro_recall', 'macro_f1']
    for col in metrics:
        summary_df[col] = pd.to_numeric(summary_df[col], errors='coerce')

    print("=== PODSUMOWANIE WYNIKÓW (MACRO F1) ===")
    top_models = summary_df.sort_values('macro_f1', ascending=False)
    print(top_models[['model', 'prompt_variant', 'accuracy', 'macro_f1']].to_string(index=False))

    sns.set_theme(style="whitegrid")

    plt.figure(figsize=(10, 6))
    summary_df['Model_Prompt'] = summary_df['model'] + ' (' + summary_df['prompt_variant'] + ')'
    plot_df = summary_df.sort_values('macro_f1', ascending=False)

    sns.barplot(data=plot_df, x='macro_f1', y='Model_Prompt', hue='model', dodge=False)
    plt.title('Porównanie Macro F1 Score - Modele vs Prompty')
    plt.xlabel('Macro F1 Score')
    plt.ylabel('Model (Wariant promptu)')
    plt.xlim(0, 1.0)
    plt.legend(title='Model', bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    plt.show()


    plt.figure(figsize=(8, 5))
    sns.lineplot(data=summary_df, x='prompt_variant', y='accuracy', hue='model', marker='o')
    plt.title('Wpływ szczegółowości promptu na Accuracy')
    plt.xlabel('Wariant promptu')
    plt.ylabel('Accuracy')
    plt.ylim(0, 1.0)
    plt.tight_layout()
    plt.show()


    best_combo = top_models.iloc[0]
    best_model = best_combo['model']
    best_prompt = best_combo['prompt_variant']

    best_preds = predictions_df[(predictions_df['model'] == best_model) &
                                (predictions_df['prompt_variant'] == best_prompt)].copy()

    y_true = best_preds['true_label'].astype(str)
    y_pred = best_preds['predicted_label'].astype(str)


    labels = sorted(list(set(y_true.unique()).union(set(y_pred.unique()))))

    cm = confusion_matrix(y_true, y_pred, labels=labels)
    plt.figure(figsize=(12, 10))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', xticklabels=labels, yticklabels=labels)
    plt.title(f'Macierz Błędów (Confusion Matrix)\nNajlepszy model: {best_model} ({best_prompt})')
    plt.xlabel('Przewidziana kategoria (Predykcja)')
    plt.ylabel('Prawdziwa kategoria (Ground Truth)')
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    plt.show()


if __name__ == '__main__':
    analyze_llm_results('llm_grid_results.csv')