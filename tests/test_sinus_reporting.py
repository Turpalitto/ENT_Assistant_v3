import unittest

from ENT_Module.sinus_reporting import build_ct_sinus_report


class SinusReportingTests(unittest.TestCase):
    def test_build_ct_sinus_report_detects_bilateral_maxillary_disease_and_omc_risk(self):
        report = build_ct_sinus_report(
            [
                {
                    "segment": "sinus_maxillary_right",
                    "volume_ml": 14.0,
                    "air_fraction": 0.22,
                    "soft_fraction": 0.74,
                    "fluid_fraction": 0.18,
                    "inferior_soft_fraction": 0.82,
                    "superior_soft_fraction": 0.31,
                },
                {
                    "segment": "sinus_maxillary_left",
                    "volume_ml": 16.0,
                    "air_fraction": 0.52,
                    "soft_fraction": 0.42,
                    "fluid_fraction": 0.05,
                    "inferior_soft_fraction": 0.50,
                    "superior_soft_fraction": 0.38,
                },
                {
                    "segment": "sinus_ethmoid_right",
                    "volume_ml": 3.0,
                    "air_fraction": 0.35,
                    "soft_fraction": 0.60,
                    "fluid_fraction": 0.08,
                    "inferior_soft_fraction": 0.66,
                    "superior_soft_fraction": 0.41,
                },
                {
                    "segment": "sinus_ethmoid_left",
                    "volume_ml": 3.5,
                    "air_fraction": 0.85,
                    "soft_fraction": 0.12,
                    "fluid_fraction": 0.01,
                    "inferior_soft_fraction": 0.16,
                    "superior_soft_fraction": 0.08,
                },
                {"segment": "nasal_cavity_right", "volume_ml": 4.0},
                {"segment": "nasal_cavity_left", "volume_ml": 9.0},
            ],
            {"dicomModality": "CT"},
        )
        self.assertIn("риносинусита", report["impression"])
        self.assertTrue(any("ОМК справа" in row["details"] or "справа" in row["details"] for row in report["findingRows"]))
        self.assertTrue(any("перегородки носа" in row["details"] for row in report["findingRows"]))
        self.assertGreater(report["lundMackay"]["totalScore"], 0)
        self.assertTrue(report["surgicalPlanning"]["summaryLines"])

    def test_build_ct_sinus_report_handles_near_normal_case(self):
        report = build_ct_sinus_report(
            [
                {
                    "segment": "sinus_maxillary_right",
                    "volume_ml": 15.0,
                    "air_fraction": 0.96,
                    "soft_fraction": 0.03,
                    "fluid_fraction": 0.0,
                    "inferior_soft_fraction": 0.04,
                    "superior_soft_fraction": 0.02,
                },
                {
                    "segment": "sinus_maxillary_left",
                    "volume_ml": 14.5,
                    "air_fraction": 0.95,
                    "soft_fraction": 0.04,
                    "fluid_fraction": 0.0,
                    "inferior_soft_fraction": 0.05,
                    "superior_soft_fraction": 0.02,
                },
            ],
            {"dicomModality": "CT"},
        )
        self.assertIn("не выявлено", report["impression"])
        self.assertIn("Пневматизация", report["description"])
        self.assertEqual(report["lundMackay"]["totalScore"], 0)


if __name__ == "__main__":
    unittest.main()
