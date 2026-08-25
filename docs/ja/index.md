---
source_sha: bc1c06f06cdb21735ec4f9b4470111666ef1434eb35434d61fbf4fe13e925db2
translated: machine
---

# Python の O 記法：時間計算量と空間計算量リファレンス

Python の操作の計算量に関する総合ガイドへようこそ。本サイトでは、Python の組み込み操作と標準ライブラリ関数の時間計算量と空間計算量、そして Python のバージョンや実装による挙動の違いをまとめています。

## 対象読者

本リファレンスは、効率的なコードを書き、データ構造とアルゴリズムについて根拠のある選択をしたい **Python 開発者**に向けたものです。アルゴリズムとデータ構造を学ぶ**情報系の学生**や、計算量の分析がよく問われる**技術面接の準備をしているエンジニア**にも役立ちます。

本サイトは Python のチュートリアルでも、
[O 記法](https://en.wikipedia.org/wiki/Big_O_notation){ target="_blank" rel="noopener" aria-label="O 記法の Wikipedia 記事を開く" }
:material-open-in-new:
の入門解説でも**ありません**。Python の基礎をすでに理解しており、時間計算量と空間計算量の概念をおおまかに把握していることを前提としています。

## クイックスタート

- **[組み込み](builtins/index.md)** - 組み込み型・関数・定数の計算量分析
- **[標準ライブラリ](stdlib/index.md)** - collections、heapq、bisect などのモジュール
- **[実装](implementations/index.md)** - CPython、PyPy、Jython などの実装ごとの詳細
- **[バージョン](versions/index.md)** - Python バージョンごとの変更と最適化

## なぜ重要なのか

計算量を理解すると、次のことができるようになります。

- 性能の高い Python コードを書く
- 用途に合ったデータ構造を選ぶ
- 入力が大きくなったときのスケールの仕方を予測する
- アルゴリズムを効果的に最適化する

## 例：リストの操作

リストの操作の計算量はさまざまです。

| 操作 | 時間計算量 | 空間 |
|-----------|-----------------|-------|
| `append()` | 償却 O(1) | - |
| `insert(0, x)` | O(n) | - |
| `pop()` | O(1) | - |
| `pop(0)` | O(n) | - |
| `in`（探索） | O(n) | - |
| `sort()` | O(n log n) | O(n) |

詳しい分析は[リスト](builtins/list.md)を参照してください。

## 本ガイドの使い方

1. **検索** - 検索バーで特定の操作を探す
2. **閲覧** - 型やモジュールからたどる
3. **絞り込み** - Python のバージョンや実装を選ぶ
4. **備考を確認** - 実装固有の注意点を読む

## 収録範囲

- **Python バージョン**：3.10-3.14
- **実装**：CPython、PyPy、Jython、IronPython
- **操作**：組み込みと標準ライブラリを合わせて 2,200 以上
- **更新**：Python の新しいリリースに合わせて定期的に更新

## このドキュメントが信頼できる理由

本ドキュメントは、複数の AI コーディングエージェント（Amp、Claude、Gemini CLI、Kiro、Copilot、Codex）とモデル（Opus 4.5+、Sonnet 4.5、Gemini 3 Pro、gpt-5.2+ など）が人間のコントリビューターと協力してレビューし、改善してきたものです。エージェントごとに視点が異なり、見つける問題も異なるため、十分な相互検証が働きます。拡充を続けているユニットテスト群が、記載された計算量を実際の Python の挙動と照らし合わせて検証しています。

さらに本プロジェクトは**完全なオープンソース**です。誰でも内容をレビューし、[問題を報告](https://github.com/heikkitoivonen/python-time-space-complexity/issues)したり、[改善を提案](https://github.com/heikkitoivonen/python-time-space-complexity/pulls)したりできます。出典はすべて明示しており、記述は Python の公式ドキュメントと CPython のソースコードに基づいています。

## コントリビュート

誤りを見つけた、あるいは内容を追加したいときは、[コントリビューションガイド](https://github.com/heikkitoivonen/python-time-space-complexity/blob/main/CONTRIBUTING.md)をご覧ください。

## 参考資料

- [Python 公式ドキュメント](https://docs.python.org/3/)
- [TimeComplexity Wiki](https://wiki.python.org/moin/TimeComplexity)
- [CPython のソースコード](https://github.com/python/cpython)と実装の詳細
- [性能テスト](https://github.com/heikkitoivonen/python-time-space-complexity/tree/main/tests)とベンチマーク

---

**免責事項**：正確さを期していますが、計算量の特性は具体的な文脈、入力サイズ、実装の詳細によって変わることがあります。性能が重要なコードでは、必ずベンチマークで確認してください。
