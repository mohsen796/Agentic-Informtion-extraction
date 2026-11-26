# Evaluation metrics

This guide describes how to assess a research-paper question-answering agent. Evaluation should use human-labelled reference answers and the paper passages that support them. Without these, scores may not reflect whether an answer is correct or properly grounded.

## Answer correctness

Answer correctness measures whether the generated answer is factually consistent with the reference (ground-truth) answer. For simple factual or numeric questions, answers can be compared by exact match after appropriate normalization (for example, equivalent units). More complex answers may need semantic comparison or an LLM judge to account for equivalent wording and partial coverage.

For a set of $N$ questions, exact-match accuracy is:

$$
\text{Answer accuracy} = \frac{\text{number of answers matching the reference}}{N}
$$

The matching rule should be specified; exact match is strict and may mark a correct paraphrase as wrong.

## Faithfulness / groundedness

Faithfulness measures whether factual claims in an answer are supported by the evidence retrieved from the available papers. Evaluate at claim level: split the response into factual claims, then check each claim against the retrieved context. A claim is supported when that context provides evidence for it.

$$
\text{Faithfulness} = \frac{\text{number of supported claims}}{\text{total number of claims}}
$$

For example, if an answer says a trial enrolled 120 patients and reduced symptoms by 30%, each statement is checked against the retrieved paper passages. An answer can be factually correct yet unfaithful if its claims are not supported by the evidence retrieved for that response.

## Citation correctness

Citation correctness measures whether citations identify the right source and provide evidence for the claims they accompany. Check three aspects:

| Aspect | What to check |
| --- | --- |
| Citation support | Does the cited passage support the associated claim? |
| Source accuracy | Is the correct paper cited? |
| Citation completeness | Do factual claims have appropriate citations? |

One simple citation support rate is:

$$
\text{Citation support rate} = \frac{\text{claim citations supported by their cited passages}}{\text{claim citations assessed}}
$$

This rate measures support only; source accuracy and completeness should also be reported or reviewed separately.

## Answerability

Answerability measures whether the question can be answered from the available papers. Label each question as:

| Category | Expected system behavior |
| --- | --- |
| Answerable | Provide an evidence-based answer. |
| Partially answerable | Answer the supported parts and acknowledge what is missing. |
| Unanswerable | Abstain or explain that the papers do not provide the information. |

This is a classification task: compare predicted labels with human-labelled labels in a confusion matrix. Precision, recall, and F1-score can be calculated per category; report the averaging method (for example, macro-F1) when combining categories. For a category treated as positive:

$$
\text{Precision} = \frac{TP}{TP+FP}, \qquad
\text{Recall} = \frac{TP}{TP+FN}, \qquad
\text{F1} = 2 \cdot \frac{\text{Precision} \cdot \text{Recall}}{\text{Precision}+\text{Recall}}
$$

Here, $TP$, $FP$, and $FN$ are true positives, false positives, and false negatives.

## Evaluation practice

An LLM-as-a-judge can help assess semantic correctness, claim support, and citation quality at scale. Its judgments should be validated against human assessments, since judges can miss unsupported details or favor particular wording. Use clear annotation criteria and retain the reference answer and supporting evidence so scores can be checked and reproduced.
