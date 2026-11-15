# Kakuyu Lib

```python
from src import Kakuyu

result = Kakuyu().login(10000, "password")
if result.success:
    print(result.message)
```

通信エラーやログイン画面から必要な値を取得できない場合は、`LoginResult.success`
が `False` になり、`message` に内容が設定されます。同時に `RuntimeWarning` が発生するため、
必要に応じて `warnings` で記録方法を変更できます。引数の形式が不正な場合は
`ValueError` が発生します。