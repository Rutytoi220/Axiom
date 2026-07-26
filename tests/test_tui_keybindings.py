import pytest
from unittest.mock import patch, MagicMock
from axiom.config import AxiomConfig, AuthMode, set_config
from prompt_toolkit.key_binding import KeyPressEvent

def test_cycle_auth_mode_binding():
    # Because `run_cli` is synchronous and sets up the bindings inside the function scope,
    # it's tricky to unit test without modifying the file structure to expose `_cycle_auth_mode`.
    # However, since `run_cli` instantiates the bindings we can mock `PromptSession` and capture the bindings.
    
    with patch('prompt_toolkit.PromptSession') as mock_session:
        with patch('rich.console.Console'):  # Prevent actual printing
            with patch('prompt_toolkit.application.run_in_terminal') as mock_run_in_terminal:
                # We need `run_cli` to exit its while True loop, so we mock `session.prompt` to raise EOFError
                mock_session.return_value.prompt.side_effect = EOFError
                
                from axiom.api.cli import run_cli
                
                # Reset state to BASIC
                config = AxiomConfig()
                config.auth_mode = AuthMode.BASIC
                set_config(config)
                
                run_cli()
                
                # `PromptSession` was instantiated with `key_bindings=bindings`
                _, kwargs = mock_session.call_args
                bindings = kwargs.get('key_bindings')
                assert bindings is not None
                
                # Find the binding for 's-tab'
                handlers = bindings.get_bindings_for_keys(('s-tab',))
                assert len(handlers) > 0
                handler = handlers[0]
                
                # Execute the handler (mocking event)
                mock_event = MagicMock(spec=KeyPressEvent)
                
                # BASIC -> AUTOPILOT
                handler.call(mock_event)
                from axiom.config import get_config
                assert get_config().auth_mode == AuthMode.AUTOPILOT
                
                # AUTOPILOT -> STRICT
                handler.call(mock_event)
                assert get_config().auth_mode == AuthMode.STRICT
                
                # STRICT -> BASIC
                handler.call(mock_event)
                assert get_config().auth_mode == AuthMode.BASIC
                
                # Verify that run_in_terminal was NOT called (no banner spam) and invalidate WAS called
                assert mock_run_in_terminal.call_count == 0
                mock_event.app.invalidate.assert_called()
