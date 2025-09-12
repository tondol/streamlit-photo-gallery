# streamlit-photo-gallery

Streamlit で作るシンプル＆高速な写真ギャラリーアプリです。

## 特徴
- 指定ディレクトリ内の画像をサムネイル付きで一覧表示
- サブディレクトリ切り替え、並び替え、1行あたりの表示数調整
- サムネイルは自動生成＆キャッシュで高速表示
- 画像の拡大プレビュー、キーボード操作（J/K）で前後移動
- 複数選択＆一括削除、個別削除も可能
- 一度削除したファイルは元に戻せません

## 必要条件
- Python 3.8+
- [Streamlit](https://streamlit.io/)
- [Pillow](https://python-pillow.org/)

## インストール
```bash
pip install -r requirements.txt
```

## 使い方
```bash
streamlit run app.py -- [-d 画像ディレクトリのパス]
```

- デフォルトはカレントディレクトリ（`-d` 省略時）
- 例: `streamlit run app.py -- -d ~/Pictures`

## スクリーンショット
TBD

## ライセンス
MIT License
