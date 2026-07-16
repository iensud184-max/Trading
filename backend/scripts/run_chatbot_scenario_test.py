def make_test_interceptor(original_func, captured_list):
    def wrapper(auth_header, message, **kwargs):
        captured_list.append(kwargs)
        return original_func(auth_header, message, **kwargs)
    return wrapper

def evaluate_scenario(captured: dict, expected: dict) -> dict:
    tool_match = captured.get("tool_name") == expected.get("tool_name")
    
    cap_args = captured.get("arguments") or {}
    exp_args = expected.get("arguments") or {}
    args_match = True
    for k, v in exp_args.items():
        if cap_args.get(k) != v:
            args_match = False
            break
            
    status = "PASS" if (tool_match and args_match) else "FAIL"
    return {
        "status": status,
        "tool_match": tool_match,
        "args_match": args_match
    }
