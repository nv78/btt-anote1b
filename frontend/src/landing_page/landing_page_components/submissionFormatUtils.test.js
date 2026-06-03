import {
  buildQuestionsExport,
  buildSampleJson,
  normalizeParsedSubmissionJson,
  parseSubmissionCsvText,
} from "./submissionFormatUtils";

describe("submission format helpers", () => {
  test("buildSampleJson prefers allowed outputs for discrete-label datasets", () => {
    const sample = JSON.parse(buildSampleJson("text_classification", [10, 11, 12], ["World", "Sports"]));

    expect(sample).toEqual([
      { id: 10, output: "World" },
      { id: 11, output: "Sports" },
      { id: 12, output: "World" },
    ]);
  });

  test("buildQuestionsExport includes options and allowed outputs in JSON", () => {
    const exported = JSON.parse(buildQuestionsExport({
      format: "json",
      sourceSentences: ["Pick one"],
      sentenceIds: [7],
      questionOptions: [[
        { label: "A", text: "Alpha" },
        { label: "B", text: "Beta" },
      ]],
      allowedOutputs: ["A", "B"],
    }));

    expect(exported).toEqual([
      {
        id: 7,
        question: "Pick one",
        options: [
          { label: "A", text: "Alpha" },
          { label: "B", text: "Beta" },
        ],
        allowed_outputs: ["A", "B"],
      },
    ]);
  });

  test("normalizeParsedSubmissionJson accepts array output aliases", () => {
    const parsed = normalizeParsedSubmissionJson([
      { id: "4", prediction: "positive" },
      { sentence_id: "not-a-number", answer: "negative" },
    ]);

    expect(parsed).toEqual({
      modelResults: ["positive", "negative"],
      sentenceIds: [4, 1],
    });
  });

  test("normalizeParsedSubmissionJson accepts submit_model body shape", () => {
    const parsed = normalizeParsedSubmissionJson({
      modelResults: ["yes", "no"],
      sentence_ids: [0, 2],
    });

    expect(parsed).toEqual({
      modelResults: ["yes", "no"],
      sentenceIds: [0, 2],
    });
  });

  test("parseSubmissionCsvText accepts output and id columns", () => {
    const parsed = parseSubmissionCsvText("id,output\n3,positive\n4,negative\n");

    expect(parsed).toEqual({
      modelResults: ["positive", "negative"],
      sentenceIds: [3, 4],
    });
  });
});
