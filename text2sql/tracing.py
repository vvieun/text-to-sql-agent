import os

_enabled = bool(os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY"))
_client = None

if _enabled:
    try:
        from langfuse import observe, get_client

        _client = get_client()
    except Exception:
        _enabled = False

if not _enabled:
    def observe(*args, **kwargs):
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]

        def decorator(fn):
            return fn

        return decorator


def record_generation(model, prompt, output, usage):
    if not _enabled:
        return
    try:
        _client.update_current_generation(
            model=model,
            input=prompt,
            output=output,
            usage_details={"input": usage.input_tokens, "output": usage.output_tokens},
        )
    except Exception:
        pass


def flush():
    if _enabled:
        try:
            _client.flush()
        except Exception:
            pass
