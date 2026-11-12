"""Focused checks for GROBID TEI to JSON conversion."""

import unittest

from preparation.analyze_paper import parse_tei


class ParseTeiTest(unittest.TestCase):
    def test_extracts_requested_document_sections(self) -> None:
        tei = """<TEI xmlns="http://www.tei-c.org/ns/1.0">
          <teiHeader><fileDesc><titleStmt><title>Paper title</title></titleStmt>
            <publicationStmt><date when="2024"/></publicationStmt>
            <sourceDesc><biblStruct><analytic><author>
              <persName><forename>Ada</forename><surname>Lovelace</surname></persName>
              <affiliation><orgName>Analytical Engine Lab</orgName>
                <address><country>UK</country></address></affiliation>
            </author><idno type="DOI">10.1234/paper</idno></analytic>
              <monogr><title level="j">Journal</title></monogr>
            </biblStruct></sourceDesc>
          </fileDesc><profileDesc><abstract><p>Paper abstract</p></abstract>
            <textClass><keywords><term>keyword</term></keywords></textClass>
          </profileDesc></teiHeader>
          <text><body><div><head>Methods</head><p>First paragraph.</p>
            <div><head>Participants</head><p>Second paragraph.</p></div>
          </div><div><head>Results</head><p>Third paragraph.</p></div></body>
          <back><listBibl><biblStruct xml:id="ref1"><analytic>
            <title>Reference title</title><author><persName><surname>Writer</surname></persName></author>
          </analytic><monogr><title>Journal</title><imprint><date when="2020"/></imprint>
            <idno type="DOI">10.1234/ref</idno></monogr></biblStruct></listBibl></back>
          <figure xml:id="fig1"><label>Figure 1</label><head>Caption</head>
            <graphic url="figure.png"/></figure>
          <figure type="table"><label>Table 1</label><head>Scores</head><table>
            <row><cell>Group</cell><cell>Score</cell></row>
            <row><cell>A</cell><cell>10</cell></row>
          </table></figure></text>
        </TEI>"""

        paper = parse_tei(tei)

        self.assertEqual(paper["title"], "Paper title")
        self.assertEqual(paper["abstract"], "Paper abstract")
        self.assertEqual(paper["date"], "2024")
        self.assertEqual(paper["doi"], "10.1234/paper")
        self.assertEqual(paper["journal"], "Journal")
        self.assertEqual(paper["authors"][0]["name"], "Ada Lovelace")
        self.assertEqual(
            paper["authors"][0]["affiliations"], ["Analytical Engine Lab, UK"]
        )
        self.assertEqual(paper["keywords"], ["keyword"])
        self.assertEqual(
            [section["section"] for section in paper["text"]],
            ["Methods", "Methods / Participants", "Results"],
        )
        self.assertEqual(paper["references"][0]["doi"], "10.1234/ref")
        self.assertEqual(paper["figures"][0]["caption"], "Caption")
        self.assertEqual(paper["tables"][0]["rows"][1], ["A", "10"])


if __name__ == "__main__":
    unittest.main()
