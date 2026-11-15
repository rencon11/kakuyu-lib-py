import html
import http.cookiejar
import re
import urllib.error
import urllib.parse
import urllib.request
import warnings
from dataclasses import dataclass


origin = "https://gaihaku-maizuru.mogsmile.com"
_INIT_PATH = "/gaihaku/student/login!init.action"
_TLOGIN_INIT_PATH = "/gaihaku/student/tlogin!init.action"
_TLOGIN_ACTION_PATH = "/gaihaku/student/tlogin.action"
_REGIST_INIT_PATH = "/gaihaku/student/regist/regist!init.action"
_TOKEN_RE = re.compile(
    r"<input\b(?=[^>]*\bname\s*=\s*['\"]token['\"])"
    r"(?=[^>]*\bvalue\s*=\s*(['\"])(.*?)\1)[^>]*>",
    re.IGNORECASE,
)
_ACTION_RE = re.compile(
    r"\baction\s*=\s*(['\"])(.*?)\1",
    re.IGNORECASE,
)


@dataclass
class LoginResult:
    success: bool
    login_token: str | None = None
    session_token: str | None = None
    message: str = ""

@dataclass
class AuthResult:
    success: bool
    remember_token: str | None = None
    message: str = ""


def _warn_failure(message: str) -> LoginResult:
    warnings.warn(message, RuntimeWarning, stacklevel=3)
    return LoginResult(success=False, message=message)


def _warn_auth_failure(message: str) -> AuthResult:
    warnings.warn(message, RuntimeWarning, stacklevel=3)
    return AuthResult(success=False, message=message)


def _extract_form_values(body: str, form_id: str) -> tuple[str | None, str | None]:
    form_re = re.compile(
        rf"<form\b(?=[^>]*\bid\s*=\s*['\"]{re.escape(form_id)}['\"])([^>]*)>(.*?)</form>",
        re.IGNORECASE | re.DOTALL,
    )
    form_match = form_re.search(body)
    if not form_match:
        return None, None
    attrs, inner_html = form_match.group(1), form_match.group(2)
    token_match = _TOKEN_RE.search(inner_html)
    action_match = _ACTION_RE.search(attrs)
    token = html.unescape(token_match.group(2)) if token_match else None
    action = html.unescape(action_match.group(2)) if action_match else None
    return token, action


class Kakuyu:
    def __init__(self, remember_token: str | None = None) -> None:
        self._cookie_jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._cookie_jar)
        )
        if remember_token:
            self._set_remember_cookie(remember_token)

    def _get_cookie(self, name: str) -> str | None:
        for cookie in self._cookie_jar:
            if cookie.name == name:
                return cookie.value
        return None

    def _set_remember_cookie(self, remember_token: str) -> None:
        parsed = urllib.parse.urlparse(origin)
        cookie = http.cookiejar.Cookie(
            version=0,
            name="remember-me",
            value=remember_token,
            port=None,
            port_specified=False,
            domain=parsed.hostname or "",
            domain_specified=False,
            domain_initial_dot=False,
            path="/gaihaku",
            path_specified=True,
            secure=parsed.scheme == "https",
            expires=None,
            discard=True,
            comment=None,
            comment_url=None,
            rest={"HttpOnly": None},
            rfc2109=False,
        )
        self._cookie_jar.set_cookie(cookie)

    def login(
        self,
        gakusekiNo: int | None = None,
        password: str | None = None,
        *,
        remember_token: str | None = None,
    ) -> LoginResult:
        if remember_token is not None:
            if not remember_token:
                raise ValueError("Arg 'remember_token' must not be empty.")
            return self.login_with_token(remember_token)

        if gakusekiNo is None and password is None:
            existing_token = self._get_cookie("remember-me")
            if existing_token:
                return self.login_with_token(existing_token)
            raise ValueError("Arg 'gakusekiNo' is required.")

        if gakusekiNo is None:
            raise ValueError("Arg 'gakusekiNo' is required.")
        if password is None:
            raise ValueError("Arg 'password' is required.")

        gakuseki_no = str(gakusekiNo)
        if not 4 <= len(gakuseki_no) <= 5:
            raise ValueError("Arg 'gakusekiNo' must be between four and five characters long.")
        if not password:
            raise ValueError("Arg 'password' is required.")
        if len(password) > 20:
            raise ValueError("Arg 'password' must be twenty characters or less.")

        try:
            init_request = urllib.request.Request(
                urllib.parse.urljoin(origin, _INIT_PATH)
            )
            with self._opener.open(init_request) as response:
                body = response.read().decode("utf-8")
                token, action = _extract_form_values(body, "login")

            if not token or not action:
                return _warn_failure("Failed to get the login form token or action.")

            data = {
                "struts.token.name": "token",
                "token": token,
                "gakusekiNo": gakuseki_no,
                "loginPass": password,
                "rememberMe": "true",
                "__checkbox_rememberMe": "true",
                "method:login": "ログイン",
            }
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            login_request = urllib.request.Request(
                urllib.parse.urljoin(origin, action),
                data=urllib.parse.urlencode(data).encode("utf-8"),
                method="POST",
                headers=headers,
            )
            with self._opener.open(login_request) as response:
                result = response.read().decode("utf-8")

            return LoginResult(
                success=True,
                login_token=result,
                session_token=self._get_cookie("JSESSIONID"),
                message="Login succeeded and a two-step verification email was sent.",
            )
        except (
            urllib.error.HTTPError,
            urllib.error.URLError,
            TimeoutError,
            UnicodeDecodeError,
        ) as error:
            return _warn_failure(f"Login request failed: {error}")

    def login_with_token(self, remember_token: str) -> LoginResult:
        if not remember_token:
            raise ValueError("Arg 'remember_token' is required.")

        self._set_remember_cookie(remember_token)
        try:
            request = urllib.request.Request(
                urllib.parse.urljoin(origin, _REGIST_INIT_PATH)
            )
            with self._opener.open(request) as response:
                final_url = response.geturl()
                body = response.read().decode("utf-8")

            if _INIT_PATH in final_url or _extract_form_values(body, "login") != (None, None):
                return _warn_failure("Login with remember-me token failed: redirected to login page.")

            return LoginResult(
                success=True,
                login_token=body,
                session_token=self._get_cookie("JSESSIONID"),
                message="Login with remember-me token succeeded.",
            )
        except (
            urllib.error.HTTPError,
            urllib.error.URLError,
            TimeoutError,
            UnicodeDecodeError,
        ) as error:
            return _warn_failure(f"Login with remember-me token failed: {error}")

    def authCode(self, code: int | str) -> AuthResult:
        code_str = str(code)
        if len(code_str) != 5 or not code_str.isdigit():
            raise ValueError("Arg 'code' must be five digits long.")

        if not self._get_cookie("JSESSIONID"):
            return _warn_auth_failure("Session cookie not found. Please call login() first.")

        try:
            tlogin_init_url = urllib.parse.urljoin(origin, _TLOGIN_INIT_PATH)
            init_request = urllib.request.Request(tlogin_init_url)
            with self._opener.open(init_request) as response:
                body = response.read().decode("utf-8")
                token, action = _extract_form_values(body, "tlogin")

            if not token:
                return _warn_auth_failure("Failed to get the tlogin form token.")

            post_path = action or _TLOGIN_ACTION_PATH
            data = {
                "struts.token.name": "token",
                "token": token,
                "authCode": code_str,
                "method:confirm": "ログイン",
            }
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": origin,
                "Referer": tlogin_init_url,
            }
            tlogin_request = urllib.request.Request(
                urllib.parse.urljoin(origin, post_path),
                data=urllib.parse.urlencode(data).encode("utf-8"),
                method="POST",
                headers=headers,
            )
            with self._opener.open(tlogin_request) as response:
                response.read()

            remember_token = self._get_cookie("remember-me")
            if not remember_token:
                return _warn_auth_failure("Failed to obtain remember-me token.")

            return AuthResult(
                success=True,
                remember_token=remember_token,
                message="Two-step verification succeeded.",
            )
        except (
            urllib.error.HTTPError,
            urllib.error.URLError,
            TimeoutError,
            UnicodeDecodeError,
        ) as error:
            return _warn_auth_failure(f"Auth code request failed: {error}")

    auth_code = authCode


__all__ = ["Kakuyu", "LoginResult", "AuthResult"]
