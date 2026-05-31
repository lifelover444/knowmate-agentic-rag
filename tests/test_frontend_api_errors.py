import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_frontend_formats_fastapi_validation_errors_without_object_object():
    script = """
        import { readFileSync } from 'node:fs';
        import { Buffer } from 'node:buffer';
        import ts from './frontend/node_modules/typescript/lib/typescript.js';

        const source = readFileSync('./frontend/src/utils/api.ts', 'utf-8');
        const output = ts.transpileModule(source, {
          compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
        }).outputText;
        const moduleUrl = `data:text/javascript;base64,${Buffer.from(output).toString('base64')}`;
        const { formatApiError } = await import(moduleUrl);

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

        const importMessage = formatApiError({
          detail: {
            failures: [{ row: 2, question: '缺少答案', error: '答案不能为空' }],
          },
        });

        if (importMessage.includes('[object Object]')) {
          throw new Error(importMessage);
        }
        if (!importMessage.includes('答案不能为空')) {
          throw new Error(importMessage);
        }
    """
    subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
