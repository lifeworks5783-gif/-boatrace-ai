#!/usr/bin/env python3
"""Regression tests for the research-only independent ChatGPT PDCA."""
import csv
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

SOURCE=Path(__file__).resolve().parents[1]/"collectors/evaluate_chatgpt_independent_pdca.py"
spec=importlib.util.spec_from_file_location("independent_pdca",SOURCE)
model=importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)

CONFIG={"model_version":"unit_test","hypothesis_frozen_on":"2026-10-14",
        "score_formula":{"morning_weight":.65,"exhibition_time_z_points":1.5},
        "plackett_luce_temperature":14.0,
        "signal_rules":{"consensus_gap_min":8.0,"upset_live_lift_min":5.0}}

class IndependentPDCA(unittest.TestCase):
    def boats(self,n=6):
        return [{"race_id":"202610130401","boat":str(i),"score":str(76-i*5),
                 "exhibition_time":str(6.70+i*.02),
                 "exhibition_course":str(i),"exhibition_f":"False"} for i in range(1,n+1)]

    def scores(self,n):
        return {("202610130401",i):float(80-i*4) for i in range(1,n+1)}

    def test_all_120_and_60_tickets_unique(self):
        for n,expected in ((5,60),(6,120)):
            board,signal,picks=model.propose(self.boats(n),self.scores(n),"202610130401",CONFIG)
            self.assertEqual(len(board),n)
            self.assertEqual(len(picks),expected)
            self.assertEqual(len(set(picks)),expected)
            self.assertTrue(all(len(set(ticket.split("-")))==3 for ticket in picks))
            self.assertIn(signal, ("consensus_axis","upset_watch","neutral_or_uncertain"))
            self.assertEqual(len(model.propose(self.boats(n),self.scores(n),"202610130401",CONFIG,baseline=True)[2]),expected)

    def test_exhibition_shift_changes_evidence_but_not_source(self):
        boats=self.boats()
        before=[dict(x) for x in boats]
        boats[2]["exhibition_time"]="6.50"
        board,_,tickets=model.propose(boats,self.scores(6),"202610130401",CONFIG)
        self.assertNotEqual(board[0]["exhibition_bonus"],None)
        self.assertEqual(len(tickets),120)
        self.assertEqual(before[0]["score"],boats[0]["score"])

    def test_real_outcome_never_enters_prediction(self):
        x=self.boats()
        old=model.propose(x,self.scores(6),"202610130401",CONFIG)
        replay=model.propose(x,self.scores(6),"202610130401",CONFIG)
        self.assertEqual(old,replay)

    def test_five_starter_result_settlement(self):
        previous=os.getcwd()
        with tempfile.TemporaryDirectory() as folder:
            try:
                os.chdir(folder)
                base=Path("predictions/2026/10/13")
                (base/"live").mkdir(parents=True)
                day=Path("archive/2026/10/13")
                day.mkdir(parents=True)
                def save(path,rows):
                    path.parent.mkdir(parents=True,exist_ok=True)
                    with path.open("w",newline="",encoding="utf-8") as f:
                        w=csv.DictWriter(f,fieldnames=list(rows[0]))
                        w.writeheader()
                        w.writerows(rows)
                rows=self.boats(5)
                save(base/"live/live_predictions_final_20261013.csv",rows)
                morn=[{"race_id":"202610130401","boat":str(i),"score":str(80-i*4)} for i in range(1,7)]
                save(base/"morning_predictions_20261013.csv",morn)
                save(day/"results_20261013_all.csv",[{"race_id":"20261013_04_01","trifecta":"1-2-3","trifecta_pay":"1200"}])
                result,quality=model.day_rows("20261013",CONFIG)
                self.assertEqual(len(result),1)
                self.assertEqual(result[0]["observed_starters"],5)
                self.assertEqual(len(result[0]["proposed8_tickets"]),8)
                self.assertEqual(quality["included"],1)
                self.assertEqual(quality["official"],1)
                self.assertTrue(result[0]["baseline8_stake"]==800)
            finally:
                os.chdir(previous)

if __name__=="__main__":
    unittest.main()
