# おまじない メインの機能をインポートします
from kakuyu import Kakuyu

# インスタンス化
kakuyu = Kakuyu()

# kakuyu.login(学籍番号, パスワード)
kakuyu.login(00000, "password")

# kakuyu.authCode(送信されたメールの5桁の認証コード)
kakuyu.authCode(00000)