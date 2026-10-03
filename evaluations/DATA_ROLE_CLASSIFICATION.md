# BOAT RACE AI データ役割分類（6区分）

更新日: 2026-10-03
基準: mainに実在する収集データ・履歴特徴量・直前スナップショット

## 設計原則
基礎実体は「選手・モーター・ボート」の3つ。
各実体を朝/直前に分ける。場・コース・気象・水面などは独立した第4ステータスではなく、根拠を検証したうえで3実体へ作用するバフ/デバフ候補として扱う。
同じ観測値を複数実体へ関連付けることは許すが、実計算での二重・三重評価は禁止する。

## 1. 選手 × 朝
### 基礎ステータス候補
- registration_no / racer_name: 識別
- grade: 級別。基礎能力に含めるか補正にするかは二重評価を避けて検証
- national_win_rate / national_top2_rate: 公式全国成績
- local_win_rate / local_top2_rate: 当地成績。選手×場補正候補
- racer_features: last5 / last10 / d30 / d90 の avg_finish, win_rate, top2_rate, top3_rate
- racer_features: avg_st, F/L率, avg_exhibition, 30日対90日トレンド
- series_results_raw / 今節着順列: 当該レースより前だけを使用する今節状態
- 前5節着順列: 直近シリーズ状態

### 朝から使えるバフ/デバフ候補
- 枠番（朝は枠=想定コースとして扱う場合）
- racer_course_features: 選手×コース d30/d90 の1着率・2連対率・3連対率・平均着順・平均ST等
- racer_venue_features: 選手×場 d30/d90 の同指標
- venue_course_features: 場×コース d30/d90 の同指標
- age / weight_kg / branch: 保存済み。直接採用せず単体・交互作用検証後に判断

## 2. 選手 × 直前
### 直前補正候補
- exhibition_course: 展示進入。選手×実進入コース適性へ接続
- exhibition_st_raw / exhibition_st_seconds / exhibition_st_flag: 展示ST・F
- exhibition_time: 選手にも関係するが機力との混合観測値
- tilt: チルト
- weight_kg: 当日値
- fixed_course: 進入固定
- weather / air_temperature_c / water_temperature_c
- wind_speed_mps / wind_direction / wind_direction_code
- wave_height_cm
- stabilizer
- deadline / collected_at: 予測時点・リーク防止管理

### 注意
展示タイム・気象水面は選手/モーター/ボートすべてに関係し得る。複数に同率で掛けない。場×コース×気象などの実績差を検証して反映先を決める。

## 3. モーター × 朝
### 基礎ステータス候補
- motor_no: 場×番号で識別
- programの motor_top2_rate
- motor_features d30/d90:
  - starts / avg_finish
  - win_rate
  - top2_rate
  - top3_rate
  - avg_st
  - avg_exhibition
  - F/L率（搭乗選手要因を含むため採用注意）
  - unique_racers
  - 30日対90日トレンド
- history_first_date / history_last_date / history_starts: 母数・信頼性判定用

### 朝補正候補
- venue_code: モーター番号は場ごとの実体
- 直近30日対90日の変化: 機力状態の上昇/下降候補
- 選手との組み合わせ: 単体性能→追加改善量を検証してから採用

## 4. モーター × 直前
### 直前補正候補
- exhibition_time: 機力状態の観測候補
- exhibition_st: 選手要因が大きいためモーターへ直接重複加算しない
- change_parts: 部品交換
- tilt: セッティング変化との交互作用候補
- water_temperature_c / wind / wave: モーター×水面条件の交互作用候補
- stabilizer
- exhibition_course: 展示条件の変化として関連候補

## 5. ボート × 朝
### 基礎ステータス候補
- boat_no: 場×番号で識別
- programの boat_top2_rate
- boat_features d30/d90:
  - starts / avg_finish
  - win_rate
  - top2_rate
  - top3_rate
  - avg_st
  - avg_exhibition
  - F/L率（搭乗選手要因を含むため採用注意）
  - unique_racers
  - 30日対90日トレンド
- history_first_date / history_last_date / history_starts: 母数・信頼性判定用

### 朝補正候補
- venue_code
- 直近30日対90日の変化
- 選手/モーターとの組み合わせは追加改善量を検証

## 6. ボート × 直前
### 直前補正候補
- exhibition_time: ボート・モーター・選手の混合観測値
- tilt
- water_temperature_c / wind / wave
- stabilizer
- exhibition_course
- change_parts: 原則モーター側だが、展示状態全体の説明変数として関連付け可

## 3実体に横断して作用する環境データ
- venue_code / venue_name
- 枠番・コース・展示進入
- venue_course_features
- weather
- air_temperature_c
- water_temperature_c
- wind_speed_mps
- wind_direction
- wave_height_cm
- fixed_course
- stabilizer

これらは「場だから+点」のように直接加算せず、全国基準に対する実績差・交互作用を確認して補正倍率候補を作る。

## 場×コース補正の基礎
既存 features/venue_course_features.csv に30日/90日の win_rate, top2_rate, top3_rate が存在する。
全国同コース基準を別途算出し、
- venue_course_win_ratio = 場×コース1着率 / 全国同コース1着率
- venue_course_top2_ratio = 場×コース2連対率 / 全国同コース2連対率
- venue_course_top3_ratio = 場×コース3連対率 / 全国同コース3連対率
を候補とする。
最終補正は母数・期間安定性・標準検証結果を確認して決定する。

## 結果検証専用（予測入力禁止）
- finish / 実着順
- actual_st / 実ST
- actual_course / 本番進入（予測時点で未確定なら禁止）
- 3連単結果
- 払戻
- 人気
結果はラベルとしてのみ使用する。

## 今後の検証順
1. 各項目単体: 1着一致 / TOP3整合 / 完全一致
2. 選手基礎ステータス候補の比較
3. モーター単体・ボート単体
4. 選手+モーター / 選手+ボート / モーター+ボート
5. 3実体合成
6. 場×コース等の朝バフ/デバフを1つずつ追加
7. 直前補正を1つずつ追加
8. 朝○→直前○ / ○→× / ×→○ / ×→× を必ず確認
9. 複数日・別期間で再現性確認
10. 根拠と結果を保存してから本番採否を判断

## 現在確認できた主要ソース
- features/racer_features.csv
- features/racer_course_features.csv
- features/racer_venue_features.csv
- features/motor_features.csv
- features/boat_features.csv
- features/venue_course_features.csv
- daily_inputs/YYYY/MM/DD/program_entries_YYYYMMDD.csv
- daily_inputs/YYYY/MM/DD/live/snapshots/*/beforeinfo_entries_YYYYMMDD.csv
- daily_inputs/YYYY/MM/DD/live/snapshots/*/beforeinfo_races_YYYYMMDD.csv

履歴特徴量生成は as_of_date 当日以降の結果を除外する leakage guard を持つ。
