# ComfyUI Model Downloader カスタムノード

HuggingFaceとCivitAIからモデルを直接ダウンロードできるComfyUIカスタムノードです。

## インストール方法

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/tori29umai0123/ComfyUI-Model_Downloader.git
```


### APIキーの設定（必須: CivitAI、オプション: HuggingFace）

CivitAIモデル(必須)や、HuggingFaceのプライベート/Gatedモデルをダウンロードする場合、APIキーの設定が必要です。

#### config.iniファイルでの設定

```bash
cd ComfyUI/custom_nodes/model_downloader
cp config.ini.example config.ini
# config.iniを編集してAPIキーを記入
```

**config.ini の例:**
```ini
[API_KEYS]
# CivitAI API Key (多くのモデルで必須)
civitai_api_key = xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# HuggingFace Token (プライベート/Gatedモデル用、オプション)
huggingface_token = hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**APIキーの取得方法:**
- **CivitAI** (必須): https://civitai.com/user/account
  - "API Keys" セクションで "Add API Key" をクリック
  - 401 Unauthorized エラーを回避するために必要
  
- **HuggingFace** (オプション): https://huggingface.co/settings/tokens
  - "Read access to contents of all public gated repos you can access" を選択
  - プライベートリポジトリやGatedモデル（Llama 2, SDXL等）用

**セキュリティ上の注意:**
- config.iniにはAPIキーが含まれるため、Gitにコミットしないでください
- .gitignoreに自動的に追加されています

## 使い方

### ノード1: Model Downloader (HF/CivitAI)

個別のモデルをダウンロードするノードです。

#### ノードの追加

1. ComfyUIを起動
2. 右クリック → `Add Node` → `utils` → `Model Downloader (HF/CivitAI)`

### 入力パラメータ

#### 必須項目

- **url**: ダウンロードするモデルのURL
  - HuggingFace: `https://huggingface.co/username/repo/resolve/main/model.safetensors`
  - CivitAI: `https://civitai.com/api/download/models/123456`

- **subdirectory**: 保存先のサブディレクトリ（models以下）
  - 例: `checkpoints`, `loras`, `controlnet`, `embeddings`
  - **ネスト対応**: `loras/SDXL`, `controlnet/lineart`, `checkpoints/anime/sdxl`
  - スラッシュ(/)またはバックスラッシュ(\)でサブディレクトリを区切れます
  - セキュリティのため、`..`による親ディレクトリ参照は禁止されています

- **filename**: 保存するファイル名（省略可）
  - 空の場合はURLから自動検出

**自動バックアップ機能**
- ダウンロード情報は自動的にカスタムノード直下の `models.ini` に保存されます
- この`models.ini`は、ModelDownloaderFromINIノードで読み込んで一括ダウンロードに使用できます

#### オプション項目

- **expected_hash**: SHA-256ハッシュ（検証用、省略可）
  - 指定すると、ダウンロード後にファイルの整合性を検証

- **max_retries**: 最大リトライ回数（デフォルト: 3）

- **update_directory_ini**: ディレクトリダウンロード時のINI更新（デフォルト: False）
  - `True`: ディレクトリ構造が変更された場合、models.iniを更新
  - `False`: models.iniを更新しない（推奨）
  - ディレクトリダウンロード時のみ有効
  - 既存ファイルは常にスキップされます

**注意**: APIキーは`config.ini`ファイルで設定します（UIからの入力は不要）

### 出力

- **status**: ダウンロード結果のステータスメッセージ
- **file_path**: ダウンロードされたファイルの完全パス

### ノード2: Model Downloader from INI

models.iniファイルから複数のモデルを一括ダウンロードするノードです。

#### ノードの追加

1. ComfyUIを起動
2. 右クリック → `Add Node` → `utils` → `Model Downloader from INI`

#### 入力パラメータ

##### 必須項目

- **ini_file_path**: INIファイルのパス
  - 空欄の場合: カスタムノード直下の `models.ini` を使用（デフォルト）
  - 指定する場合: 任意のパスを指定可能
  - 対応形式:
    - `"E:\desktop\model1.ini"` (ダブルクォート付き、バックスラッシュ)
    - `E:\desktop\model2.ini` (クォートなし、バックスラッシュ)
    - `E:/desktop/model3.ini` (スラッシュ)
    - `models.ini` (相対パス - カスタムノードディレクトリからの相対)

##### オプション項目

- **max_retries**: 最大リトライ回数（デフォルト: 3）
- **skip_existing**: 既存ファイルをスキップ（デフォルト: True）
- **update_directory_ini**: ディレクトリ構造変更時にINIを更新（デフォルト: False）
  - ディレクトリダウンロードで、ファイル数やパスが変更された場合のみINIを更新

#### 出力

- **status**: 一括ダウンロードの結果サマリー
- **summary**: 詳細な統計情報

## 使用例

### 例1: HuggingFaceからLoRAをダウンロード

```
URL: https://huggingface.co/tori29umai/lineart/resolve/main/sdxl_BWLine.safetensors
Subdirectory: loras
Filename: sdxl_BWLine.safetensors
```

### 例2: CivitAIからControlNetをダウンロード

```
URL: https://civitai.com/api/download/models/515749?type=Model&format=SafeTensor
Subdirectory: controlnet
Filename: (空欄でOK - 自動検出)
Expected Hash: 58bae8a373d6a39b33a5d110c5b22894fc86b7b1e189b05b163e69446c7f48ee
```

### 例3: カスタムパスに保存

```
URL: https://huggingface.co/stabilityai/sdxl-turbo/resolve/main/sd_xl_turbo_1.0.safetensors
Subdirectory: checkpoints/sdxl
Filename: sdxl_turbo.safetensors
```

### 例4: ネストされたディレクトリに保存

```
URL: https://huggingface.co/tori29umai/lineart/resolve/main/sdxl_BWLine.safetensors
Subdirectory: loras/SDXL/lineart
Filename: sdxl_BWLine.safetensors
```

### 例5: 複数階層のディレクトリ構造

```
URL: https://huggingface.co/cagliostrolab/animagine-xl-3.1/resolve/main/animagine-xl-3.1.safetensors
Subdirectory: checkpoints/anime/sdxl/animagine
Filename: animagine-xl-3.1.safetensors
```

### 例6: HuggingFaceディレクトリごとダウンロード 🆕

```
URL: https://huggingface.co/2vXpSwA7/iroiro-lora/tree/main/qwen_lora
Subdirectory: loras/qwen
Filename: (空欄 - ディレクトリ内の全ファイルをダウンロード)
```

**動作:**
- `qwen_lora` ディレクトリ内の全ファイルを自動検出
- ディレクトリ構造を維持して `loras/qwen/` 以下に保存
- サブディレクトリも再帰的にダウンロード
- **既存ファイルは自動的にスキップ**（重複ダウンロードを防止）
- `update_directory_ini=False`（デフォルト）: models.iniは更新しない
- `update_directory_ini=True`: ディレクトリ構造が変更された場合のみmodels.iniを更新

**対応URL形式:**
```
https://huggingface.co/{user}/{repo}/tree/{revision}/{directory_path}

例:
- https://huggingface.co/2vXpSwA7/iroiro-lora/tree/main/qwen_lora
- https://huggingface.co/user/repo/tree/main
- https://huggingface.co/user/repo/tree/main/subfolder/deep
```

## models.ini による環境再現

### 自動記録機能

モデルをダウンロードすると、自動的にカスタムノードディレクトリ直下の `models.ini` に記録されます。

**INIファイルの場所:**
```
ComfyUI/custom_nodes/model_downloader/models.ini
```

**models.ini の例:**
```ini
[sdxl_BWLine_safetensors]
url = https://huggingface.co/tori29umai/lineart/resolve/main/sdxl_BWLine.safetensors
subdirectory = loras/SDXL
filename = sdxl_BWLine.safetensors
filepath = loras/SDXL/sdxl_BWLine.safetensors
hash = 07c59708361b3e2e4f0b0c0f232183f5f39c32c31b6b6981b4392ea30d49dd57
timestamp = 2024-11-27 12:34:56

[animagine-xl-3_1_safetensors]
url = https://huggingface.co/cagliostrolab/animagine-xl-3.1/resolve/main/animagine-xl-3.1.safetensors
subdirectory = checkpoints
filename = animagine-xl-3.1.safetensors
filepath = checkpoints/animagine-xl-3.1.safetensors
hash = e3c47aedb06418c6c331443cd89f2b3b3b34b7ed2102a3d4c4408a8d35aad6b0
timestamp = 2024-11-27 12:35:10
```

### 別PCでの環境再現手順

1. **元のPCでmodels.iniを取得**
   ```bash
   # models.iniをコピー
   cp ComfyUI/custom_nodes/model_downloader/models.ini ~/backup/
   ```

2. **新しいPCにmodels.iniを配置**
   ```bash
   # 新しいPCで（カスタムノードインストール後）
   cp ~/backup/models.ini ComfyUI/custom_nodes/model_downloader/
   ```

3. **ComfyUIで一括ダウンロード**
   - `Model Downloader from INI` ノードを追加
   - `ini_file_path` を空欄のまま実行（カスタムノード直下のmodels.iniを使用）
   - または、カスタムパスを指定

### 手動でmodels.iniを編集

models.iniを手動で編集して、カスタムモデルリストを作成することもできます。

```ini
[my_custom_model]
url = https://huggingface.co/username/repo/resolve/main/model.safetensors
subdirectory = loras
filename = custom_model.safetensors
hash = <optional_sha256_hash>
```

## 特徴

### URL自動判定

URLを入力すると、自動的にHuggingFaceかCivitAIかを判定し、適切な方法でダウンロードします。

### ネストされたディレクトリ対応

`loras/SDXL`や`checkpoints/anime/sdxl`のように、複数階層のサブディレクトリを指定できます。
- スラッシュ(`/`)またはバックスラッシュ(`\`)でディレクトリを区切れます
- 指定されたディレクトリ構造が存在しない場合は自動的に作成されます
- セキュリティのため、`..`による親ディレクトリ参照は禁止されています

例:
```
checkpoints/anime/sdxl/animagine  → models/checkpoints/anime/sdxl/animagine/
loras/SDXL                        → models/loras/SDXL/
controlnet/lineart/v2             → models/controlnet/lineart/v2/
```

### ハッシュ検証

SHA-256ハッシュを指定すると、ダウンロード後にファイルの整合性を自動検証します。
ハッシュが一致しない場合は自動的にリトライします。

### 既存ファイルの処理

同名のファイルが既に存在する場合:
1. ハッシュが指定されている → 検証して一致すればスキップ
2. ハッシュが指定されていない → 再ダウンロードせずにスキップ

### エラーハンドリング

- ネットワークエラー時は自動リトライ
- ハッシュ不一致時は自動リトライ
- 最大リトライ回数に達したらエラーメッセージを表示

## トラブルシューティング

### ダウンロードが失敗する

- インターネット接続を確認
- URLが正しいか確認
- CivitAIの場合、APIキーが必要な場合があります

### ハッシュ検証が失敗する

- ハッシュ値が正しいか確認（大文字小文字は無視されます）
- ファイルが破損している可能性があるため、再ダウンロードを試す

### ファイルが見つからない

- ComfyUIの `models` ディレクトリを確認
- 指定したサブディレクトリが正しいか確認

## ライセンス

MIT License

## 貢献

バグ報告や機能リクエストは Issue でお願いします。
