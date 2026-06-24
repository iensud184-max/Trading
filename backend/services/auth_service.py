import jwt

def get_user_id_from_header(auth_header: str) -> tuple[str, str]:
    """
    Authorization 헤더의 Bearer 토큰으로부터 user_id(sub)와 토큰을 파싱합니다.
    """
    if not auth_header or not auth_header.startswith("Bearer "):
        raise Exception("유효하지 않은 인증 헤더입니다.")
    token = auth_header.split(" ")[1]
    # JWT 서명 검증은 Supabase API 호출 단계에서 대행하므로, 여기서는 디코딩만 처리
    payload = jwt.decode(token, options={"verify_signature": False})
    user_id = payload.get("sub")
    if not user_id:
        raise Exception("토큰 페이로드가 유효하지 않습니다.")
    return user_id, token
