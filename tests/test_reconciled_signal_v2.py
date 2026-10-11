"""Regression: never freeze obsolete F0R0 and never call an unknown live signal off."""
from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "collectors"))
from prediction_history_guard import preserve_closed_prediction
from build_family_race_compare_page import nontrigger_signal_diagnostic_html, signal_recheck_pending_html
from build_latest_prediction_view import build_up_signal, build_down_signal, build_signal_ai_prediction, load_signal_ai_config
from evaluate_signal_ai_performance import load_live, _signal_inputs
from audit_signal_consistency import corrected_v2_replay_history

JST = timezone(timedelta(hours=9))
V1 = "fujin_raijin_pipeline_v1_20261009"
V2 = "fujin_raijin_pipeline_v2_20261011"


class ObsoleteSignalReconciliationTests(unittest.TestCase):
    def _case(self, model, active, *, recovery=True):
        return {
            "race_id": "20261011-23-06",
            "prediction_type": "直前",
            "deadline": "2026-10-11T10:53:00+09:00",
            "generated_at": "2026-10-11T10:50:00+09:00",
            "signal_logic_identity": {"model_version": model},
            "retrospective_signal_recovery": recovery,
            "up_signal": {"available": True, "level": 3 if active else 0},
            "down_signal": {"available": True, "level": 0},
            "signal_ai_prediction": {"signal_key": "F0R3",
                "combinations": [
                    {"combination": f"{a}-{b}-{c}"}
                    for a in range(1,7) for b in range(1,7) for c in range(1,7)
                    if a != b and a != c and b != c
                ][:24]} if active else {},
            "prediction_quality": {"status":"recovered_observation"}
        }

    def test_retrospective_v1_nontrigger_can_be_replaced_by_verified_v2(self):
        old = self._case(V1, False)
        new = self._case(V2, True)
        result = preserve_closed_prediction(old, new, datetime(2026,10,11,14,0,tzinfo=JST))
        self.assertIs(result, new)

    def test_same_version_finished_recovered_signal_remains_immutable(self):
        old = self._case(V2, True)
        new = self._case(V2, False)
        result = preserve_closed_prediction(old, new, datetime(2026,10,11,14,0,tzinfo=JST))
        self.assertIs(result, old)

    def test_unverified_or_unavailable_signal_cannot_override_old_model(self):
        old = self._case(V1, False)
        new = self._case(V2, True)
        new["up_signal"]["available"] = False
        self.assertIs(preserve_closed_prediction(old,new,datetime(2026,10,11,14,0,tzinfo=JST)),old)

    def test_real_karatsu_6r_v1_gate_wrong_v2_rank_free_r3(self):
        races = load_live("20261011")
        boats = _signal_inputs(sorted(races["202610112306"],
                    key=lambda x: int(x["rank"])))
        v1=build_up_signal(boats, outside_live_top3=True)
        v2=build_up_signal(boats, outside_live_top3=False)
        down=build_down_signal(boats)
        self.assertEqual(v1["level"],0)
        self.assertEqual(v2["level"],3)
        self.assertEqual(down["level"],0)
        self.assertTrue(any(c["boat"]==6 and c["rank"]==2 for c in v2["candidates"]))
        model = build_signal_ai_prediction(boats,v2,down,load_signal_ai_config())
        self.assertEqual(model["signal_key"],"F0R3")
        self.assertEqual(len(model["combinations"]),24)
        replay=corrected_v2_replay_history(ROOT,"20261011")["202610112306"]
        self.assertEqual(int(replay["new_raijin_level"]),3)
        self.assertEqual(int(replay["new_actual_rank"]),57)

    def test_no_signal_reason_uses_saved_model_rank_policy(self):
        up={"available": True,"level":0,"thresholds":{"level1_rise_min":7.5}}
        down={"available": True,"level":0,"metrics":{}}
        old=nontrigger_signal_diagnostic_html(up,down,{"signal_logic_identity":{"model_version":V1}})
        new=nontrigger_signal_diagnostic_html(up,down,{"signal_logic_identity":{"model_version":V2}})
        self.assertIn("直前4位以下",old)
        self.assertIn("直前順位に関係なく",new)
        self.assertNotIn("直前上位3艇以外に",new)
        self.assertEqual(signal_recheck_pending_html({"raw":{"prediction_type":"直前",
            "up_signal":{"available":True},"down_signal":{"available":True}}}),"")
        self.assertIn("直前シグナル再照合待ち",
            signal_recheck_pending_html({"raw":{"prediction_type":"直前",
              "up_signal":{"available":False},"down_signal":{"available":False}}}))


if __name__ == "__main__":
    unittest.main()
