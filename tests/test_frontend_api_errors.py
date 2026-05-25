import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_frontend_formats_fastapi_validation_errors_without_object_object():
    script = """
        import { formatApiError } from './frontend/src/apiErrors.js';

        const message = formatApiError({
          detail: [
            {
              loc: ['body', 'chunking_config', 'chunk_size'],
              msg: 'Input should be greater than or equal to 50',
            },
          ],
        });

        if (message.includes('[object Object]')) {
          throw new Error(message);
        }
        if (!message.includes('chunking_config.chunk_size')) {
          throw new Error(message);
        }
        if (!message.includes('Input should be greater than or equal to 50')) {
          throw new Error(message);
        }
    """
    subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
