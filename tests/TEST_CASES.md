# sqr 测试用例文档

> 本文档对 `tests/` 下 92 个测试用例逐一规格化，每个用例包含：**用例描述 / 测试步骤 / 预期结果 / 优先级**。
>
> - **基线**：`python3 -m pytest tests/ -q` → 92 passed
> - **编号规则**：`TC-<MODULE>-<NNN>`，模块代码见下表
> - **优先级**：P0 = 核心链路（失败即致命）/ P1 = 关键功能 / P2 = 边界与异常

| 模块代码 | 测试文件 | 用例数 |
|----------|----------|--------|
| PROTO | `test_protocol.py` | 34 |
| COMP | `test_compressor.py` | 8 |
| CHUNK | `test_chunker.py` | 21 |
| QR | `test_qr_render.py` | 19 |
| RT | `test_roundtrip.py` | 10 |
| **合计** | | **92** |

---

## 目录

- [1. 协议层 — `test_protocol.py`](#1-协议层--test_protocolpy)
  - [1.1 TestComputeFileId（file_id 计算）](#11-testcomputefileidfile_id-计算)
  - [1.2 TestComputeCrc32（CRC32 计算）](#12-testcomputecrc32crc32-计算)
  - [1.3 TestComputeHashes（哈希计算）](#13-testcomputehashes哈希计算)
  - [1.4 TestChunkEncodeDecode（Chunk 编解码对称性）](#14-testchunkencodedecodechunk-编解码对称性)
  - [1.5 TestChunkDecodeErrors（Chunk 解码错误拒绝）](#15-testchunkdecodeerrorschunk-解码错误拒绝)
  - [1.6 TestChunkCrc（Chunk CRC 校验）](#16-testchunkcrcchunk-crc-校验)
  - [1.7 TestChunkFrameType（帧类型判定）](#17-testchunkframetype帧类型判定)
  - [1.8 TestFileManifest（文件清单）](#18-testfilemanifest文件清单)
- [2. 压缩层 — `test_compressor.py`](#2-压缩层--test_compressorpy)
- [3. 分片层 — `test_chunker.py`](#3-分片层--test_chunkerpy)
- [4. QR 渲染层 — `test_qr_render.py`](#4-qr-渲染层--test_qr_renderpy)
- [5. 端到端 — `test_roundtrip.py`](#5-端到端--test_roundtrippy)
- [附录：用例统计](#附录用例统计)

---

# 1. 协议层 — `test_protocol.py`

> 覆盖 `sqr.protocol` 模块：纯函数、Chunk 编解码、FileManifest、错误路径。
> **P0 用例集中区**——协议层失败会导致整个传输链路崩溃。

## 1.1 TestComputeFileId（file_id 计算）

### TC-PROTO-001 | `test_takes_first_12_chars`

- **代码位置**：`tests/test_protocol.py:30` — `TestComputeFileId.test_takes_first_12_chars`
- **描述**：验证 `compute_file_id` 正确截取 SHA-256 的前 12 个字符作为 file_id。
- **前置**：无
- **步骤**：
  1. 构造长度为 64 的字符串 `"a" * 64`（模拟完整 SHA-256 hex）。
  2. 调用 `compute_file_id("a" * 64)`。
- **预期**：返回值为 `"aaaaaaaaaaaa"`（长度恰好 12）。
- **优先级**：P2

### TC-PROTO-002 | `test_short_hash`

- **代码位置**：`tests/test_protocol.py:34` — `TestComputeFileId.test_short_hash`
- **描述**：当输入哈希短于 12 字符时，应原样返回不补齐。
- **前置**：无
- **步骤**：
  1. 输入 `"abc123"`（长度 6）。
  2. 调用 `compute_file_id("abc123")`。
- **预期**：返回值为 `"abc123"`（与输入相等，未补长）。
- **优先级**：P2

## 1.2 TestComputeCrc32（CRC32 计算）

### TC-PROTO-003 | `test_empty_string`

- **代码位置**：`tests/test_protocol.py:39` — `TestComputeCrc32.test_empty_string`
- **描述**：空字符串的 CRC32 应为 0。
- **前置**：无
- **步骤**：调用 `compute_crc32("")`。
- **预期**：返回 `0`。
- **优先级**：P1

### TC-PROTO-004 | `test_empty_bytes`

- **代码位置**：`tests/test_protocol.py:42` — `TestComputeCrc32.test_empty_bytes`
- **描述**：空 bytes 的 CRC32 应为 0（与空字符串等价）。
- **前置**：无
- **步骤**：调用 `compute_crc32(b"")`。
- **预期**：返回 `0`。
- **优先级**：P1

### TC-PROTO-005 | `test_known_value`

- **代码位置**：`tests/test_protocol.py:45` — `TestComputeCrc32.test_known_value`
- **描述**：`compute_crc32` 结果应与标准库 `binascii.crc32`（zlib 多项式）一致。
- **前置**：无
- **步骤**：
  1. 计算 `expected = binascii.crc32(b"hello") & 0xFFFFFFFF`。
  2. 调用 `compute_crc32("hello")`。
- **预期**：返回值等于 `expected`。
- **优先级**：P0

### TC-PROTO-006 | `test_str_and_bytes_match`

- **代码位置**：`tests/test_protocol.py:51` — `TestComputeCrc32.test_str_and_bytes_match`
- **描述**：str 与等价 bytes 输入应产生相同的 CRC32。
- **前置**：无
- **步骤**：分别调用 `compute_crc32("abc")` 和 `compute_crc32(b"abc")`。
- **预期**：两个返回值相等。
- **优先级**：P1

### TC-PROTO-007 | `test_unsigned`

- **代码位置**：`tests/test_protocol.py:54` — `TestComputeCrc32.test_unsigned`
- **描述**：CRC32 返回值必须始终为 unsigned 32-bit（不能为负）。
- **前置**：无
- **步骤**：
  1. 构造 `b"\x00" * 100`（可能触发有符号实现的负数路径）。
  2. 调用 `compute_crc32(data)`。
- **预期**：返回值满足 `0 <= result <= 0xFFFFFFFF`。
- **优先级**：P1

## 1.3 TestComputeHashes（哈希计算）

### TC-PROTO-008 | `test_sha256_known`

- **代码位置**：`tests/test_protocol.py:63` — `TestComputeHashes.test_sha256_known`
- **描述**：空输入的 SHA-256 应等于 NIST 标准已知向量。
- **前置**：无
- **步骤**：调用 `compute_sha256(b"")`。
- **预期**：返回 `"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"`。
- **优先级**：P0

### TC-PROTO-009 | `test_md5_known`

- **代码位置**：`tests/test_protocol.py:69` — `TestComputeHashes.test_md5_known`
- **描述**：空输入的 MD5 应等于 RFC 1321 已知向量。
- **前置**：无
- **步骤**：调用 `compute_md5(b"")`。
- **预期**：返回 `"d41d8cd98f00b204e9800998ecf8427e"`。
- **优先级**：P0

## 1.4 TestChunkEncodeDecode（Chunk 编解码对称性）

### TC-PROTO-010 | `test_encode_format`

- **代码位置**：`tests/test_protocol.py:79` — `TestChunkEncodeDecode.test_encode_format`
- **描述**：验证 Chunk.encode() 输出格式严格符合 SQ1 协议。
- **前置**：构造 `Chunk(file_id="a1b2c3d4e5f6", index=3, total=10, crc32=0x0A1B2C3D, payload="SGVsbG8=")`。
- **步骤**：调用 `chunk.encode()`。
- **预期**：返回字符串 `"SQ1|a1b2c3d4e5f6|3|10|0a1b2c3d|SGVsbG8="`（CRC 为 8 位小写 hex）。
- **优先级**：P0

### TC-PROTO-011 | `test_roundtrip_data_frame`

- **代码位置**：`tests/test_protocol.py:90` — `TestChunkEncodeDecode.test_roundtrip_data_frame`
- **描述**：数据帧 encode → decode 应严格对称。
- **前置**：构造一个 index=5、total=8 的数据帧，CRC 由 `compute_crc32("test_payload")` 计算。
- **步骤**：`decoded = Chunk.decode(original.encode())`。
- **预期**：`decoded == original`（所有字段相等）。
- **优先级**：P0

### TC-PROTO-012 | `test_roundtrip_manifest_frame`

- **代码位置**：`tests/test_protocol.py:101` — `TestChunkEncodeDecode.test_roundtrip_manifest_frame`
- **描述**：manifest 帧（index=MANIFEST_INDEX=0）的 encode/decode 对称。
- **前置**：构造 index=MANIFEST_INDEX 的 Chunk。
- **步骤**：`decoded = Chunk.decode(original.encode())`。
- **预期**：`decoded == original`。
- **优先级**：P0

### TC-PROTO-013 | `test_roundtrip_empty_payload`

- **代码位置**：`tests/test_protocol.py:112` — `TestChunkEncodeDecode.test_roundtrip_empty_payload`
- **描述**：空 payload 的 Chunk 也能正确回环。
- **前置**：构造 payload="" 的 Chunk。
- **步骤**：`decoded = Chunk.decode(original.encode())`。
- **预期**：`decoded == original`，且 `decoded.payload == ""`。
- **优先级**：P1

### TC-PROTO-014 | `test_payload_with_pipe_not_split`

- **代码位置**：`tests/test_protocol.py:123` — `TestChunkEncodeDecode.test_payload_with_pipe_not_split`
- **描述**：payload 内含 `|` 时不应被 `split` 误切（`maxsplit` 保护）。
- **前置**：构造 payload 为 `"abc|def|ghi"` 的 Chunk。
- **步骤**：
  1. `encoded = original.encode()`。
  2. `decoded = Chunk.decode(encoded)`。
- **预期**：`decoded.payload == "abc|def|ghi"`（完整保留所有 `|`）。
- **优先级**：P0

## 1.5 TestChunkDecodeErrors（Chunk 解码错误拒绝）

> 所有用例必须抛出 `ProtocolError`，并用 `match=...` 锁定错误信息关键词。

### TC-PROTO-015 | `test_wrong_version`

- **代码位置**：`tests/test_protocol.py:138` — `TestChunkDecodeErrors.test_wrong_version`
- **描述**：协议版本号不是 `SQ1` 的帧必须被拒绝。
- **前置**：无
- **步骤**：调用 `Chunk.decode("SQ2|abcdef012345|1|1|00000000|payload")`。
- **预期**：抛出 `ProtocolError`，错误信息匹配 `"version"`。
- **优先级**：P0

### TC-PROTO-016 | `test_too_few_fields`

- **代码位置**：`tests/test_protocol.py:143` — `TestChunkDecodeErrors.test_too_few_fields`
- **描述**：字段数不足（少于 6 个）的帧必须被拒绝。
- **前置**：无
- **步骤**：调用 `Chunk.decode("SQ1|abcdef012345|1|1|00000000")`（只有 5 段）。
- **预期**：抛出 `ProtocolError`，错误信息匹配 `"fields"`。
- **优先级**：P0

### TC-PROTO-017 | `test_too_many_separators_maxsplit_protects`

- **代码位置**：`tests/test_protocol.py:148` — `TestChunkDecodeErrors.test_too_many_separators_maxsplit_protects`
- **描述**：payload 含额外 `|` 时，最后一个 `|` 之后的所有内容都归 payload。
- **前置**：无
- **步骤**：调用 `Chunk.decode("SQ1|abcdef012345|1|1|00000000|pay|load")`。
- **预期**：解码成功，`chunk.payload == "pay|load"`（不抛错）。
- **优先级**：P0

### TC-PROTO-018 | `test_non_numeric_index`

- **代码位置**：`tests/test_protocol.py:155` — `TestChunkDecodeErrors.test_non_numeric_index`
- **描述**：index 字段非数字时必须被拒绝。
- **前置**：无
- **步骤**：调用 `Chunk.decode("SQ1|abcdef012345|abc|1|00000000|payload")`。
- **预期**：抛出 `ProtocolError`，错误信息匹配 `"index"`。
- **优先级**：P0

### TC-PROTO-019 | `test_non_numeric_total`

- **代码位置**：`tests/test_protocol.py:160` — `TestChunkDecodeErrors.test_non_numeric_total`
- **描述**：total 字段非数字时必须被拒绝。
- **前置**：无
- **步骤**：调用 `Chunk.decode("SQ1|abcdef012345|1|xyz|00000000|payload")`。
- **预期**：抛出 `ProtocolError`，错误信息匹配 `"total"`。
- **优先级**：P0

### TC-PROTO-020 | `test_non_hex_crc32`

- **代码位置**：`tests/test_protocol.py:165` — `TestChunkDecodeErrors.test_non_hex_crc32`
- **描述**：CRC32 字段非合法 hex 时必须被拒绝。
- **前置**：无
- **步骤**：调用 `Chunk.decode("SQ1|abcdef012345|1|1|zzzzzzzz|payload")`。
- **预期**：抛出 `ProtocolError`，错误信息匹配 `"crc32"`。
- **优先级**：P0

### TC-PROTO-021 | `test_empty_string`

- **代码位置**：`tests/test_protocol.py:170` — `TestChunkDecodeErrors.test_empty_string`
- **描述**：空字符串输入必须被拒绝（不能静默返回空 Chunk）。
- **前置**：无
- **步骤**：调用 `Chunk.decode("")`。
- **预期**：抛出 `ProtocolError`。
- **优先级**：P1

## 1.6 TestChunkCrc（Chunk CRC 校验）

### TC-PROTO-022 | `test_verify_crc_correct`

- **代码位置**：`tests/test_protocol.py:176` — `TestChunkCrc.test_verify_crc_correct`
- **描述**：CRC 字段与 payload 真实 CRC 一致时，`verify_crc()` 返回 True。
- **前置**：构造 Chunk，其 crc32 字段 = `compute_crc32(payload)`。
- **步骤**：调用 `chunk.verify_crc()`。
- **预期**：返回 `True`。
- **优先级**：P0

### TC-PROTO-023 | `test_verify_crc_wrong`

- **代码位置**：`tests/test_protocol.py:187` — `TestChunkCrc.test_verify_crc_wrong`
- **描述**：CRC 字段与 payload 真实 CRC 不一致时，`verify_crc()` 返回 False（**不抛错，返回布尔**）。
- **前置**：构造 Chunk，故意将 crc32 设为 `0xDEADBEEF`。
- **步骤**：调用 `chunk.verify_crc()`。
- **预期**：返回 `False`。
- **优先级**：P0

### TC-PROTO-024 | `test_crc_zero_padding`

- **代码位置**：`tests/test_protocol.py:197` — `TestChunkCrc.test_crc_zero_padding`
- **描述**：CRC32 = 0 在编码后应表现为 `"00000000"`（8 位 hex 零填充）。
- **前置**：构造 crc32=0 的 Chunk。
- **步骤**：调用 `chunk.encode()`。
- **预期**：返回字符串中包含 `"00000000"`。
- **优先级**：P1

## 1.7 TestChunkFrameType（帧类型判定）

### TC-PROTO-025 | `test_manifest_frame_type`

- **代码位置**：`tests/test_protocol.py:210` — `TestChunkFrameType.test_manifest_frame_type`
- **描述**：index=MANIFEST_INDEX（0）的帧类型应为 `FrameType.MANIFEST`。
- **前置**：构造 index=MANIFEST_INDEX 的 Chunk。
- **步骤**：读取 `chunk.frame_type`。
- **预期**：等于 `FrameType.MANIFEST`。
- **优先级**：P1

### TC-PROTO-026 | `test_data_frame_type`

- **代码位置**：`tests/test_protocol.py:220` — `TestChunkFrameType.test_data_frame_type`
- **描述**：普通数据帧（index=1）的帧类型应为 `FrameType.DATA`。
- **前置**：构造 index=1 的 Chunk。
- **步骤**：读取 `chunk.frame_type`。
- **预期**：等于 `FrameType.DATA`。
- **优先级**：P1

### TC-PROTO-027 | `test_data_frame_type_last`

- **代码位置**：`tests/test_protocol.py:230` — `TestChunkFrameType.test_data_frame_type_last`
- **描述**：最后一片数据帧（index=total）的帧类型仍为 `FrameType.DATA`（不因"末尾"而特殊）。
- **前置**：构造 index=5、total=5 的 Chunk。
- **步骤**：读取 `chunk.frame_type`。
- **预期**：等于 `FrameType.DATA`。
- **优先级**：P2

## 1.8 TestFileManifest（文件清单）

### TC-PROTO-028 | `test_roundtrip_with_md5`

- **代码位置**：`tests/test_protocol.py:258` — `TestFileManifest.test_roundtrip_with_md5`
- **描述**：带 MD5 的 FileManifest，其 `encode_payload` → `decode_payload` 应严格对称。
- **前置**：构造 `FileManifest(schema_version=1, filename="test.txt", original_bytes=29816, sha256="a"*64, md5="b"*32, compression="gzip", encoding="base64")`。
- **步骤**：
  1. `payload = manifest.encode_payload()`。
  2. `decoded = FileManifest.decode_payload(payload)`。
- **预期**：`decoded == manifest`（所有字段相等）。
- **优先级**：P0

### TC-PROTO-029 | `test_roundtrip_without_md5`

- **代码位置**：`tests/test_protocol.py:264` — `TestFileManifest.test_roundtrip_without_md5`
- **描述**：md5 字段为 None 时也应能回环，且解码后 md5 仍为 None。
- **前置**：构造 FileManifest，md5=None。
- **步骤**：
  1. `payload = manifest.encode_payload()`。
  2. `decoded = FileManifest.decode_payload(payload)`。
- **预期**：`decoded == manifest`，且 `decoded.md5 is None`。
- **优先级**：P0

### TC-PROTO-030 | `test_encoded_payload_is_base64`

- **代码位置**：`tests/test_protocol.py:271` — `TestFileManifest.test_encoded_payload_is_base64`
- **描述**：manifest 编码后的 payload 必须是合法 Base64 字符串。
- **前置**：构造任意 FileManifest。
- **步骤**：调用 `manifest.encode_payload()`，用正则 `^[A-Za-z0-9+/=]+$` 匹配。
- **预期**：匹配成功。
- **优先级**：P1

### TC-PROTO-031 | `test_encoded_payload_no_newline`

- **代码位置**：`tests/test_protocol.py:278` — `TestFileManifest.test_encoded_payload_no_newline`
- **描述**：manifest 编码后的 payload 不能包含换行符（防止 QR 码内出现多行）。
- **前置**：构造任意 FileManifest。
- **步骤**：调用 `manifest.encode_payload()`。
- **预期**：返回值中 `"\n" not in payload` 且 `"\r" not in payload`。
- **优先级**：P0

### TC-PROTO-032 | `test_decode_invalid_base64`

- **代码位置**：`tests/test_protocol.py:284` — `TestFileManifest.test_decode_invalid_base64`
- **描述**：非法 Base64 字符串解码 manifest 时必须被拒绝。
- **前置**：无
- **步骤**：调用 `FileManifest.decode_payload("!!!not-base64!!!")`。
- **预期**：抛出 `ProtocolError`，错误信息匹配 `"Invalid manifest"`。
- **优先级**：P0

### TC-PROTO-033 | `test_decode_missing_fields`

- **代码位置**：`tests/test_protocol.py:288` — `TestFileManifest.test_decode_missing_fields`
- **描述**：JSON 中缺少必需字段时必须被拒绝。
- **前置**：构造一个只含 `{"v": 1, "fn": "test"}` 的 Base64 payload。
- **步骤**：调用 `FileManifest.decode_payload(incomplete)`。
- **预期**：抛出 `ProtocolError`，错误信息匹配 `"missing"`。
- **优先级**：P0

### TC-PROTO-034 | `test_unicode_filename`

- **代码位置**：`tests/test_protocol.py:297` — `TestFileManifest.test_unicode_filename`
- **描述**：Unicode 文件名（中文）的 manifest 应能正确回环。
- **前置**：构造 `filename="中文文件名.txt"` 的 FileManifest。
- **步骤**：
  1. `payload = manifest.encode_payload()`。
  2. `decoded = FileManifest.decode_payload(payload)`。
- **预期**：`decoded.filename == "中文文件名.txt"`。
- **优先级**：P1

---

# 2. 压缩层 — `test_compressor.py`

> 覆盖 `sqr.sender.compressor`：gzip 压缩 + Base64 编码 + 回退逻辑。
> 发送端依赖此层把原始文件转成可分片的 Base64 payload。

## 2.1 TestCompressAndEncode

### TC-COMP-001 | `test_gzip_roundtrip`

- **代码位置**：`tests/test_compressor.py:18` — `TestCompressAndEncode.test_gzip_roundtrip`
- **描述**：`compress_and_encode(use_zstd=False)` 产出的 payload 能被 `decompress_payload` 还原为原始字节。
- **前置**：`raw = b"Hello, World! " * 100`。
- **步骤**：
  1. `result = compress_and_encode(raw, use_zstd=False)`。
  2. `compressed = base64.b64decode(result.data_b64)`。
  3. `restored = decompress_payload(compressed, result.compression)`。
- **预期**：
  - `result.compression == "gzip"`。
  - `result.encoding == "base64"`。
  - `restored == raw`。
- **优先级**：P0

### TC-COMP-002 | `test_base64_no_newline`

- **代码位置**：`tests/test_compressor.py:29` — `TestCompressAndEncode.test_base64_no_newline`
- **描述**：Base64 输出不能含换行符（QR 码无法承载多行）。
- **前置**：`raw = b"x" * 5000`（足够长以触发 Base64 默认 76 字符折行）。
- **步骤**：调用 `compress_and_encode(raw)`。
- **预期**：`"\n" not in result.data_b64` 且 `"\r" not in result.data_b64`。
- **优先级**：P0

### TC-COMP-003 | `test_base64_valid_chars`

- **代码位置**：`tests/test_compressor.py:35` — `TestCompressAndEncode.test_base64_valid_chars`
- **描述**：输出仅含标准 Base64 字符集。
- **前置**：`raw = b"test data for encoding"`。
- **步骤**：用正则 `^[A-Za-z0-9+/=]+$` 匹配 `result.data_b64`。
- **预期**：匹配成功。
- **优先级**：P1

### TC-COMP-004 | `test_empty_input`

- **代码位置**：`tests/test_compressor.py:42` — `TestCompressAndEncode.test_empty_input`
- **描述**：空输入也能正确压缩、编码、还原。
- **前置**：`raw = b""`。
- **步骤**：
  1. `result = compress_and_encode(b"")`。
  2. 解码并 `decompress_payload`。
- **预期**：
  - `result.compression == "gzip"`。
  - `restored == b""`。
- **优先级**：P1

### TC-COMP-005 | `test_unicode_input`

- **代码位置**：`tests/test_compressor.py:50` — `TestCompressAndEncode.test_unicode_input`
- **描述**：UTF-8 中文输入的回环（验证不依赖 ASCII 假设）。
- **前置**：`raw = "你好世界，EDA 工具测试。".encode("utf-8")`。
- **步骤**：
  1. `result = compress_and_encode(raw)`。
  2. 解码并 `decompress_payload`。
- **预期**：`restored == raw`。
- **优先级**：P1

### TC-COMP-006 | `test_compression_effective`

- **代码位置**：`tests/test_compressor.py:58` — `TestCompressAndEncode.test_compression_effective`
- **描述**：高重复文本经 gzip 后体积应显著缩小（验证压缩确实生效）。
- **前置**：`raw = b"SELECT * FROM commands WHERE id = 1;\n" * 200`。
- **步骤**：
  1. `result = compress_and_encode(raw)`。
  2. `compressed = base64.b64decode(result.data_b64)`。
- **预期**：`len(compressed) < len(raw)`。
- **优先级**：P2

### TC-COMP-007 | `test_zstd_fallback_to_gzip`

- **代码位置**：`tests/test_compressor.py:65` — `TestCompressAndEncode.test_zstd_fallback_to_gzip`
- **描述**：请求 zstd 但环境无 `zstandard` 库时，应自动回退 gzip，不能抛错。
- **前置**：`raw = b"test data"`。
- **步骤**：
  1. `result = compress_and_encode(raw, use_zstd=True)`。
  2. 解码并 `decompress_payload`。
- **预期**：
  - `result.compression in ("gzip", "zstd")`。
  - `restored == raw`。
- **优先级**：P1

## 2.2 TestDecompressPayload

### TC-COMP-008 | `test_invalid_compression`

- **代码位置**：`tests/test_compressor.py:77` — `TestDecompressPayload.test_invalid_compression`
- **描述**：传入不支持的压缩算法名时必须抛错（不能静默返回原数据）。
- **前置**：无
- **步骤**：调用 `decompress_payload(b"test", "bzip2")`。
- **预期**：抛出 `ValueError`，错误信息匹配 `"Unknown compression"`。
- **优先级**：P0

---

# 3. 分片层 — `test_chunker.py`

> 覆盖 `sqr.sender.chunker`：把 Base64 payload 切成多片 + 构造 manifest 帧 + `build_all_frames` 端到端。

## 3.1 TestChunkPayload（`chunk_payload`）

### TC-CHUNK-001 | `test_single_chunk`

- **代码位置**：`tests/test_chunker.py:56` — `TestChunkPayload.test_single_chunk`
- **描述**：payload 长度 < max_chars 时只产生 1 个分片。
- **前置**：构造 `data_b64="ABC"` 的 CompressedPayload，max_chars=1200。
- **步骤**：调用 `chunk_payload(compressed, "fid", max_chars=1200)`。
- **预期**：
  - 分片数 = 1。
  - `chunks[0].index == 1`，`chunks[0].total == 1`。
  - `chunks[0].payload == "ABC"`。
- **优先级**：P0

### TC-CHUNK-002 | `test_empty_payload`

- **代码位置**：`tests/test_chunker.py:64` — `TestChunkPayload.test_empty_payload`
- **描述**：空 payload 也产生 1 个分片（payload 为空），而非 0 个。
- **前置**：`data_b64=""`，max_chars=1200。
- **步骤**：调用 `chunk_payload`。
- **预期**：
  - 分片数 = 1。
  - `chunks[0].payload == ""`。
- **优先级**：P1

### TC-CHUNK-003 | `test_exact_division`

- **代码位置**：`tests/test_chunker.py:72` — `TestChunkPayload.test_exact_division`
- **描述**：长度恰好整除 max_chars 时，不产生空尾片。
- **前置**：`data_b64="A" * 300`，max_chars=100。
- **步骤**：调用 `chunk_payload`。
- **预期**：
  - 分片数 = 3（不是 4）。
  - 每片 index = i+1，total = 3。
  - 每片 payload 长度 = 100。
- **优先级**：P0

### TC-CHUNK-004 | `test_remainder`

- **代码位置**：`tests/test_chunker.py:81` — `TestChunkPayload.test_remainder`
- **描述**：不能整除时，最后一片为余数长度。
- **前置**：`data_b64="A" * 305`，max_chars=100。
- **步骤**：调用 `chunk_payload`。
- **预期**：
  - 分片数 = 4（⌈305/100⌉）。
  - `chunks[0].total == 4`。
  - `len(chunks[3].payload) == 5`。
- **优先级**：P0

### TC-CHUNK-005 | `test_one_char_remainder`

- **代码位置**：`tests/test_chunker.py:88` — `TestChunkPayload.test_one_char_remainder`
- **描述**：余数恰好为 1 字符的边界场景。
- **前置**：`data_b64="A" * 301`，max_chars=100。
- **步骤**：调用 `chunk_payload`。
- **预期**：
  - 分片数 = 4。
  - `len(chunks[3].payload) == 1`。
- **优先级**：P1

### TC-CHUNK-006 | `test_crc_correctness`

- **代码位置**：`tests/test_chunker.py:94` — `TestChunkPayload.test_crc_correctness`
- **描述**：每个分片的 crc32 字段必须等于其 payload 的真实 CRC，且 `verify_crc()` 为 True。
- **前置**：`data_b64="test_payload_data"`，max_chars=5（强制多片）。
- **步骤**：遍历所有分片。
- **预期**：对每个 chunk，`chunk.crc32 == compute_crc32(chunk.payload)` 且 `chunk.verify_crc() is True`。
- **优先级**：P0

### TC-CHUNK-007 | `test_file_id_propagation`

- **代码位置**：`tests/test_chunker.py:101` — `TestChunkPayload.test_file_id_propagation`
- **描述**：传入的 file_id 必须被复制到每个分片。
- **前置**：`file_id="my_file_id_"`。
- **步骤**：遍历所有分片。
- **预期**：每个 `chunk.file_id == "my_file_id_"`。
- **优先级**：P0

### TC-CHUNK-008 | `test_sequential_indices`

- **代码位置**：`tests/test_chunker.py:107` — `TestChunkPayload.test_sequential_indices`
- **描述**：分片 index 从 1 开始连续递增，无跳号。
- **前置**：`data_b64="X" * 500`，max_chars=100。
- **步骤**：遍历分片，比较 index 与位置 i。
- **预期**：`chunks[i].index == i + 1`（i 从 0 起）。
- **优先级**：P0

### TC-CHUNK-009 | `test_all_chunks_same_total`

- **代码位置**：`tests/test_chunker.py:113` — `TestChunkPayload.test_all_chunks_same_total`
- **描述**：所有分片的 total 字段必须一致（不能有的写 3 有的写 4）。
- **前置**：`data_b64="X" * 500`，max_chars=100。
- **步骤**：收集所有 `chunk.total` 到 set。
- **预期**：set 大小为 1。
- **优先级**：P0

### TC-CHUNK-010 | `test_payload_concatenation`

- **代码位置**：`tests/test_chunker.py:119` — `TestChunkPayload.test_payload_concatenation`
- **描述**：所有分片 payload 按顺序拼接后应等于原始 Base64。
- **前置**：`original="ABCDEFGHIJKLMNOP" * 50`，max_chars=100。
- **步骤**：`restored = "".join(c.payload for c in chunks)`。
- **预期**：`restored == original`。
- **优先级**：P0

## 3.2 TestBuildManifest（`build_manifest`）

### TC-CHUNK-011 | `test_basic_manifest`

- **代码位置**：`tests/test_chunker.py:134` — `TestBuildManifest.test_basic_manifest`
- **描述**：`build_manifest` 正确组装所有元数据字段。
- **前置**：`filename="test.txt"`，`raw=b"raw data"`（8 字节），`sha256="a"*64`，`md5="b"*32`。
- **步骤**：调用 `build_manifest`。
- **预期**：
  - `schema_version == 1`。
  - `filename == "test.txt"`。
  - `original_bytes == 8`。
  - `sha256 == "a"*64`，`md5 == "b"*32`。
  - `compression == "gzip"`，`encoding == "base64"`。
- **优先级**：P0

### TC-CHUNK-012 | `test_none_md5`

- **代码位置**：`tests/test_chunker.py:147` — `TestBuildManifest.test_none_md5`
- **描述**：md5 参数为 None 时，manifest.md5 也应为 None（不能默认填空串）。
- **前置**：md5=None。
- **步骤**：调用 `build_manifest("test.txt", b"raw", "a"*64, None, compressed)`。
- **预期**：`manifest.md5 is None`。
- **优先级**：P1

## 3.3 TestBuildManifestFrame（`build_manifest_frame`）

### TC-CHUNK-013 | `test_manifest_frame_index_zero`

- **代码位置**：`tests/test_chunker.py:159` — `TestBuildManifestFrame.test_manifest_frame_index_zero`
- **描述**：manifest 帧的 index 必须是 MANIFEST_INDEX（0），且 frame_type 为 MANIFEST。
- **前置**：构造 manifest 和 file_id。
- **步骤**：调用 `build_manifest_frame(manifest, "a"*12, total=5)`。
- **预期**：
  - `frame.index == MANIFEST_INDEX`。
  - `frame.total == 5`。
  - `frame.file_id == "a"*12`。
  - `frame.frame_type == FrameType.MANIFEST`。
- **优先级**：P0

### TC-CHUNK-014 | `test_manifest_frame_crc`

- **代码位置**：`tests/test_chunker.py:169` — `TestBuildManifestFrame.test_manifest_frame_crc`
- **描述**：manifest 帧的 CRC 必须自洽。
- **前置**：构造 manifest 帧。
- **步骤**：调用 `frame.verify_crc()`。
- **预期**：返回 `True`。
- **优先级**：P0

### TC-CHUNK-015 | `test_manifest_frame_payload_roundtrip`

- **代码位置**：`tests/test_chunker.py:176` — `TestBuildManifestFrame.test_manifest_frame_payload_roundtrip`
- **描述**：manifest 帧的 payload 字段（Base64 编码的 manifest）能被 `FileManifest.decode_payload` 还原。
- **前置**：构造 manifest 帧。
- **步骤**：`decoded = FileManifest.decode_payload(frame.payload)`。
- **预期**：`decoded == manifest`（与原 manifest 相等）。
- **优先级**：P0

## 3.4 TestBuildAllFrames（`build_all_frames`）

### TC-CHUNK-016 | `test_small_file`

- **代码位置**：`tests/test_chunker.py:191` — `TestBuildAllFrames.test_small_file`
- **描述**：小文件经 `build_all_frames` 后，chunks[0] 为 manifest 帧，其余为数据帧，所有帧 file_id 一致、total 一致。
- **前置**：`text="Hello, EDA World!"`，max_chars=1200。
- **步骤**：调用 `build_all_frames`，检查 chunks 列表。
- **预期**：
  - `chunks[0].index == MANIFEST_INDEX`。
  - 所有 `c.index >= 1`（除 chunks[0]）。
  - 所有 `c.file_id == file_id`。
  - 所有 `c.total == len(data_chunks)`（数据帧数）。
- **优先级**：P0

### TC-CHUNK-017 | `test_multi_chunk_file`

- **代码位置**：`tests/test_chunker.py:213` — `TestBuildAllFrames.test_multi_chunk_file`
- **描述**：多分片大文件的所有帧 CRC 都通过校验。
- **前置**：用 `random.seed(42)` 生成 500 行低重复文本，max_chars=80（强制 ≥ 4 帧）。
- **步骤**：调用 `build_all_frames`，遍历 chunks 检查 CRC。
- **预期**：
  - `len(chunks) > 4`。
  - 每个 `chunk.verify_crc() is True`。
- **优先级**：P0

### TC-CHUNK-018 | `test_manifest_matches_original`

- **代码位置**：`tests/test_chunker.py:232` — `TestBuildAllFrames.test_manifest_matches_original`
- **描述**：返回的 manifest 元数据与输入文件一致。
- **前置**：`text="测试数据 EDA commands\n" * 50`。
- **步骤**：调用 `build_all_frames`，对比 manifest 字段。
- **预期**：
  - `manifest.filename == "commands.txt"`。
  - `manifest.original_bytes == len(raw)`。
  - `manifest.sha256 == sha256`，`manifest.md5 == md5`。
- **优先级**：P0

### TC-CHUNK-019 | `test_chunks_decode_roundtrip`

- **代码位置**：`tests/test_chunker.py:245` — `TestBuildAllFrames.test_chunks_decode_roundtrip`
- **描述**：每个 Chunk 的 `encode()` → `decode()` 严格对称。
- **前置**：生成 30 行文本，max_chars=100。
- **步骤**：遍历 chunks，对每个执行 `Chunk.decode(chunk.encode())`。
- **预期**：`decoded == chunk`。
- **优先级**：P0

### TC-CHUNK-020 | `test_all_frames_consistent_total`

- **代码位置**：`tests/test_chunker.py:258` — `TestBuildAllFrames.test_all_frames_consistent_total`
- **描述**：所有帧的 total 字段必须等于数据帧数（不含 manifest）。
- **前置**：80 行文本，max_chars=50。
- **步骤**：`data_total = len(chunks) - 1`，遍历检查。
- **预期**：每个 `chunk.total == data_total`。
- **优先级**：P0

### TC-CHUNK-021 | `test_all_frames_sequential_data_indices`

- **代码位置**：`tests/test_chunker.py:268` — `TestBuildAllFrames.test_all_frames_sequential_data_indices`
- **描述**：数据帧（跳过 chunks[0] manifest）的 index 必须从 1 连续递增。
- **前置**：60 行文本，max_chars=50。
- **步骤**：取 `data_chunks = chunks[1:]`，遍历比较。
- **预期**：`data_chunks[i].index == i + 1`。
- **优先级**：P0

---

# 4. QR 渲染层 — `test_qr_render.py`

> 覆盖 `sqr.sender.qr_render`：QR 矩阵生成、PPM P6 文件、Unicode half-blocks。
> **关键约束**：本层测试不导入真实 Pillow（发送端零安装）。

## 4.1 TestGenerateMatrix（`generate_matrix`）

### TC-QR-001 | `test_basic_generation`

- **代码位置**：`tests/test_qr_render.py:19` — `TestGenerateMatrix.test_basic_generation`
- **描述**：`generate_matrix` 返回合法 QRMatrix，维度符合 `version*4+17` 公式。
- **前置**：无
- **步骤**：`qr = generate_matrix("hello world")`。
- **预期**：
  - `isinstance(qr, QRMatrix)`。
  - `qr.version >= 1`。
  - `qr.module_count == qr.version * 4 + 17`。
  - `len(qr.matrix) == qr.module_count`。
  - 每行长度等于 `module_count`。
- **优先级**：P0

### TC-QR-002 | `test_matrix_is_bool`

- **代码位置**：`tests/test_qr_render.py:27` — `TestGenerateMatrix.test_matrix_is_bool`
- **描述**：矩阵每个单元必须是 Python `bool`（不是 0/1 int）。
- **前置**：`qr = generate_matrix("test")`。
- **步骤**：遍历所有单元 `isinstance(cell, bool)`。
- **预期**：全部为 True。
- **优先级**：P1

### TC-QR-003 | `test_quiet_zone_default`

- **代码位置**：`tests/test_qr_render.py:33` — `TestGenerateMatrix.test_quiet_zone_default`
- **描述**：未传 quiet_zone 时默认值为 4。
- **前置**：无
- **步骤**：`qr = generate_matrix("test")`。
- **预期**：`qr.quiet_zone == 4`。
- **优先级**：P2

### TC-QR-004 | `test_custom_quiet_zone`

- **代码位置**：`tests/test_qr_render.py:37` — `TestGenerateMatrix.test_custom_quiet_zone`
- **描述**：自定义 quiet_zone 参数生效。
- **前置**：无
- **步骤**：`qr = generate_matrix("test", quiet_zone=8)`。
- **预期**：`qr.quiet_zone == 8`。
- **优先级**：P2

### TC-QR-005 | `test_error_correction_levels`

- **代码位置**：`tests/test_qr_render.py:41` — `TestGenerateMatrix.test_error_correction_levels`
- **描述**：四种纠错级别 L/M/Q/H 都能正常生成矩阵。
- **前置**：无
- **步骤**：对 `("L", "M", "Q", "H")` 分别调用 `generate_matrix("test data", error_correction=ec)`。
- **预期**：每次返回的 `qr.version >= 1`。
- **优先级**：P1

### TC-QR-006 | `test_invalid_error_correction`

- **代码位置**：`tests/test_qr_render.py:46` — `TestGenerateMatrix.test_invalid_error_correction`
- **描述**：非法纠错级别必须被拒绝。
- **前置**：无
- **步骤**：`generate_matrix("test", error_correction="X")`。
- **预期**：抛出 `ValueError`，错误信息匹配 `"error_correction"`。
- **优先级**：P0

### TC-QR-007 | `test_larger_data_higher_version`

- **代码位置**：`tests/test_qr_render.py:50` — `TestGenerateMatrix.test_larger_data_higher_version`
- **描述**：数据量越大，QR version 越高（单调性）。
- **前置**：无
- **步骤**：
  1. `small = generate_matrix("a")`。
  2. `large = generate_matrix("a" * 500)`。
- **预期**：`large.version >= small.version`。
- **优先级**：P2

### TC-QR-008 | `test_protocol_frame_encoding`

- **代码位置**：`tests/test_qr_render.py:55` — `TestGenerateMatrix.test_protocol_frame_encoding`
- **描述**：真实 SQ1 协议帧字符串能正常生成 QR 矩阵（集成检查）。
- **前置**：`frame = "SQ1|abcdef012345|1|10|0a1b2c3d|" + "X" * 200`。
- **步骤**：`qr = generate_matrix(frame)`。
- **预期**：`qr.module_count > 0`。
- **优先级**：P1

## 4.2 TestMatrixToPpm（`matrix_to_ppm`）

### TC-QR-009 | `test_ppm_header_format`

- **代码位置**：`tests/test_qr_render.py:63` — `TestMatrixToPpm.test_ppm_header_format`
- **描述**：PPM 输出的 header 符合 P6 规范。
- **前置**：`qr = generate_matrix("test")`。
- **步骤**：`ppm = matrix_to_ppm(qr, module_size=5)`，解析前 3 个换行符。
- **预期**：header 以 `"P6\n"` 开头，且包含 `"255"`。
- **优先级**：P0

### TC-QR-010 | `test_ppm_dimensions`

- **代码位置**：`tests/test_qr_render.py:74` — `TestMatrixToPpm.test_ppm_dimensions`
- **描述**：PPM 第二行声明的宽高与 `total_modules * module_size` 一致。
- **前置**：quiet_zone=4，module_size=10。
- **步骤**：解析 PPM 第二行。
- **预期**：第二行字符串等于 `f"{expected_size} {expected_size}"`，其中 `expected_size = (module_count + 2*quiet_zone) * module_size`。
- **优先级**：P0

### TC-QR-011 | `test_ppm_pixel_data_size`

- **代码位置**：`tests/test_qr_render.py:83` — `TestMatrixToPpm.test_ppm_pixel_data_size`
- **描述**：header 之后的像素数据字节数 = `宽 × 高 × 3`（RGB）。
- **前置**：quiet_zone=4，module_size=5。
- **步骤**：`len(ppm) - header_size`。
- **预期**：等于 `(total_modules * module_size) ** 2 * 3`。
- **优先级**：P0

### TC-QR-012 | `test_ppm_has_black_and_white`

- **代码位置**：`tests/test_qr_render.py:92` — `TestMatrixToPpm.test_ppm_has_black_and_white`
- **描述**：PPM 输出必须同时包含黑色和白色像素（不能全黑/全白）。
- **前置**：`qr = generate_matrix("hello world")`，module_size=2。
- **步骤**：在 ppm 字节流中搜索 `b"\x00\x00\x00"` 和 `b"\xff\xff\xff"`。
- **预期**：两者都存在。
- **优先级**：P1

### TC-QR-013 | `test_ppm_module_size_1`

- **代码位置**：`tests/test_qr_render.py:100` — `TestMatrixToPpm.test_ppm_module_size_1`
- **描述**：module_size=1 时，PPM 像素应逐位匹配 QR 矩阵（最强不变量）。
- **前置**：`qr = generate_matrix("X", quiet_zone=0)`。
- **步骤**：对每个矩阵单元 `(r, c)`，读取对应像素。
- **预期**：
  - 矩阵为 True → 像素 `b"\x00\x00\x00"`（黑）。
  - 矩阵为 False → 像素 `b"\xff\xff\xff"`（白）。
- **优先级**：P0

## 4.3 TestMatrixToUnicode（`matrix_to_unicode`）

### TC-QR-014 | `test_returns_string`

- **代码位置**：`tests/test_qr_render.py:118` — `TestMatrixToUnicode.test_returns_string`
- **描述**：返回值类型为 str。
- **前置**：`qr = generate_matrix("test")`。
- **步骤**：`result = matrix_to_unicode(qr)`。
- **预期**：`isinstance(result, str)`。
- **优先级**：P1

### TC-QR-015 | `test_has_block_characters`

- **代码位置**：`tests/test_qr_render.py:123` — `TestMatrixToUnicode.test_has_block_characters`
- **描述**：输出只用 half-block 字符集（█▀▄）和空格。
- **前置**：`qr = generate_matrix("hello world")`。
- **步骤**：收集 `result` 中除 `\n` 外的所有字符到集合。
- **预期**：字符集是 `{"\u2588", "\u2580", "\u2584", " "}` 的子集。
- **优先级**：P1

### TC-QR-016 | `test_line_count`

- **代码位置**：`tests/test_qr_render.py:130` — `TestMatrixToUnicode.test_line_count`
- **描述**：Unicode 输出的行数符合 `(total+1)//2`（两行矩阵合并为一行字符）。
- **前置**：quiet_zone=4。
- **步骤**：`actual_lines = result.count("\n") + 1`。
- **预期**：`actual_lines == (module_count + 2*quiet_zone + 1) // 2`。
- **优先级**：P1

### TC-QR-017 | `test_nonempty_output`

- **代码位置**：`tests/test_qr_render.py:138` — `TestMatrixToUnicode.test_nonempty_output`
- **描述**：输出非空，且至少含一个非空白字符。
- **前置**：`qr = generate_matrix("hello world this is a test")`。
- **步骤**：`result = matrix_to_unicode(qr)`。
- **预期**：
  - `len(result) > 0`。
  - 存在字符 `c != " "` 且 `c != "\n"`。
- **优先级**：P2

## 4.4 TestQRMatrixProperties

### TC-QR-018 | `test_frozen`

- **代码位置**：`tests/test_qr_render.py:146` — `TestQRMatrixProperties.test_frozen`
- **描述**：QRMatrix 是不可变对象（frozen dataclass），赋值应失败。
- **前置**：`qr = generate_matrix("test")`。
- **步骤**：尝试 `qr.version = 99`。
- **预期**：抛出 `AttributeError`。
- **优先级**：P2

### TC-QR-019 | `test_finder_pattern_present`

- **代码位置**：`tests/test_qr_render.py:151` — `TestQRMatrixProperties.test_finder_pattern_present`
- **描述**：QR 码左上角应存在 Finder Pattern（7×7 黑色边框）。
- **前置**：`qr = generate_matrix("test", quiet_zone=0)`。
- **步骤**：检查矩阵特定位置。
- **预期**：
  - `m[0][0] is True`。
  - `m[6][6] is True` 或 `m[0][6] is True`。
- **优先级**：P1

---

# 5. 端到端 — `test_roundtrip.py`

> ★ **核心里程碑测试**——证明完整光学传输链路可用：
> `file → gzip/b64 → 分片 → QR → PPM → Pillow/pyzbar 解码 → 组装 → gunzip → SHA-256/MD5 校验`

## 5.1 TestRoundtrip

### TC-RT-001 | `test_small_file`

- **代码位置**：`tests/test_roundtrip.py:105` — `TestRoundtrip.test_small_file`
- **描述**：小文件（`sample_small.txt`）经完整链路后逐字节还原。
- **前置**：fixture 文件 `tests/fixtures/sample_small.txt`，max_chars=1200，module_size=10。
- **步骤**：
  1. 发送端：`build_all_frames` → 每帧 `generate_matrix` → `matrix_to_ppm` 写文件。
  2. 接收端：每帧 `decode_qr_from_file` → `assembler.add_raw`。
  3. 检查 `progress.is_complete`，`assemble` → `decompress_payload`。
  4. `verify_restored_file` 校验 SHA-256/MD5/字节。
- **预期**：
  - `result.success is True`。
  - `restored == raw`。
- **优先级**：P0

### TC-RT-002 | `test_mid_file`

- **代码位置**：`tests/test_roundtrip.py:114` — `TestRoundtrip.test_mid_file`
- **描述**：中等文件（`sample_mid.txt`）在小 max_chars（强制多分片）下也能完整还原。
- **前置**：fixture `sample_mid.txt`，max_chars=100（强制 ≥ 多帧），module_size=10。
- **步骤**：同 TC-RT-001。
- **预期**：`result.success is True` 且 `restored == raw`。
- **优先级**：P0

### TC-RT-003 | `test_repetitive_file`

- **代码位置**：`tests/test_roundtrip.py:123` — `TestRoundtrip.test_repetitive_file`
- **描述**：高重复文件（`sample_repetitive.txt`）端到端正确（验证压缩路径不丢字节）。
- **前置**：fixture `sample_repetitive.txt`，max_chars=1200，module_size=10。
- **步骤**：同 TC-RT-001。
- **预期**：`result.success is True` 且 `restored == raw`。
- **优先级**：P0

### TC-RT-004 | `test_md5_exact_match`

- **代码位置**：`tests/test_roundtrip.py:132` — `TestRoundtrip.test_md5_exact_match`
- **描述**：传输后文件的 MD5 与源文件精确相等（冗余校验生效）。
- **前置**：fixture `sample_mid.txt`，max_chars=100。
- **步骤**：同 TC-RT-001，额外检查 `result.md5_match`。
- **预期**：
  - `result.md5_match is True`。
  - `result.actual_md5 == compute_md5(raw)`。
- **优先级**：P0

### TC-RT-005 | `test_error_correction_q`

- **代码位置**：`tests/test_roundtrip.py:142` — `TestRoundtrip.test_error_correction_q`
- **描述**：使用 Q 级纠错（约 25% 容错）也能正常传输。
- **前置**：fixture `sample_small.txt`，max_chars=1200，module_size=10，error_correction="Q"。
- **步骤**：同 TC-RT-001。
- **预期**：`result.success is True`。
- **优先级**：P1

### TC-RT-006 | `test_small_module_size`

- **代码位置**：`tests/test_roundtrip.py:151` — `TestRoundtrip.test_small_module_size`
- **描述**：module_size=5（更小的物理尺寸）下 pyzbar 仍能可靠解码。
- **前置**：fixture `sample_small.txt`，max_chars=1200，module_size=5。
- **步骤**：同 TC-RT-001。
- **预期**：`result.success is True`。
- **优先级**：P1

## 5.2 TestRoundtripDataIntegrity

### TC-RT-007 | `test_byte_for_byte_match` [sample_small.txt]

- **代码位置**：`tests/test_roundtrip.py:166` — `TestRoundtripDataIntegrity.test_byte_for_byte_match`
- **描述**：对 `sample_small.txt`，max_chars=500，逐字节相等校验。
- **前置**：fixture `sample_small.txt`。
- **步骤**：
  1. 完整链路：`build_all_frames` → 每帧 QR+PPM → 解码 → 组装 → 解压。
  2. 比较 `restored` 与 `raw`。
- **预期**：
  - `restored == raw`。
  - `len(restored) == len(raw)`。
- **优先级**：P0

### TC-RT-008 | `test_byte_for_byte_match` [sample_mid.txt]

- **代码位置**：`tests/test_roundtrip.py:166` — `TestRoundtripDataIntegrity.test_byte_for_byte_match`
- **描述**：对 `sample_mid.txt` 同样逐字节校验。
- **前置**：fixture `sample_mid.txt`。
- **步骤**：同 TC-RT-007。
- **预期**：`restored == raw` 且长度相等。
- **优先级**：P0

### TC-RT-009 | `test_byte_for_byte_match` [sample_repetitive.txt]

- **代码位置**：`tests/test_roundtrip.py:166` — `TestRoundtripDataIntegrity.test_byte_for_byte_match`
- **描述**：对 `sample_repetitive.txt` 同样逐字节校验。
- **前置**：fixture `sample_repetitive.txt`。
- **步骤**：同 TC-RT-007。
- **预期**：`restored == raw` 且长度相等。
- **优先级**：P0

> **说明**：TC-RT-007/008/009 由 `@pytest.mark.parametrize("filename", FIXTURE_FILES)` 展开，源码中表现为同一个测试方法。

### TC-RT-010 | `test_chunk_count_matches`

- **代码位置**：`tests/test_roundtrip.py:198` — `TestRoundtripDataIntegrity.test_chunk_count_matches`
- **描述**：发送端生成的数据帧数 == 接收端 ChunkAssembler 收到的帧数。
- **前置**：fixture `sample_mid.txt`，max_chars=80（强制多帧）。
- **步骤**：
  1. 发送端：`build_all_frames`，记录 `data_chunk_count = len(chunks) - 1`。
  2. 接收端：完整解码 → 组装，读取 `progress.total` 和 `progress.received_count`。
- **预期**：
  - `progress.total == data_chunk_count`。
  - `progress.received_count == data_chunk_count`。
- **优先级**：P0

---

# 附录：用例统计

## A.1 按优先级分布

| 优先级 | 数量 | 占比 | 说明 |
|--------|------|------|------|
| **P0**（核心链路） | 56 | 60.9% | 失败即致命，必须立即修复 |
| **P1**（关键功能） | 25 | 27.2% | 关键但非致命 |
| **P2**（边界与异常） | 11 | 11.9% | 防御性、文档性测试 |
| **合计** | **92** | 100% | |

## A.2 按测试类别分布

| 类别 | 数量 | 代表场景 |
|------|------|----------|
| **纯函数验证** | 9 | CRC32 / SHA-256 / MD5 / file_id 计算 |
| **对称性（round-trip）** | 18 | Chunk / Manifest / 压缩的 encode↔decode |
| **错误拒绝** | 14 | 各种非法输入必须抛特定异常 |
| **边界值** | 11 | 单片 / 整除 / 余数 / 余数=1 / 空 |
| **一致性不变量** | 18 | total 一致 / index 连续 / file_id 传播 |
| **格式正确性** | 12 | PPM header / Base64 字符集 / 维度公式 |
| **端到端集成** | 10 | 完整光学链路逐字节还原 |

## A.3 测试覆盖的关键不变量

| 不变量 | 验证用例 |
|--------|----------|
| Chunk encode ↔ decode 对称 | TC-PROTO-011/012/013/014 |
| CRC32 自洽 | TC-PROTO-022/023/024, TC-CHUNK-006 |
| SHA-256 / MD5 NIST 已知向量 | TC-PROTO-008/009 |
| Payload 含 `\|` 不被误切 | TC-PROTO-014/017 |
| 分片拼接还原原 Base64 | TC-CHUNK-010 |
| 所有帧 total 一致 | TC-CHUNK-009/020 |
| 数据帧 index 连续 | TC-CHUNK-008/021 |
| PPM 像素 = 矩阵 × module_size² | TC-QR-011/013 |
| 完整光学链路逐字节相等 | TC-RT-001~009 |
| 发送/接收帧数对齐 | TC-RT-010 |

## A.4 红线（禁止行为）

任何用例的弱化都**必须在 `claude-progress.md` 当前 Session 条目显式记录理由**：

- ❌ 删除或 `pytest.skip` P0 用例
- ❌ 把 `assert` 改成 `print` / `warnings.warn`
- ❌ 放宽 CRC32 / SHA-256 / MD5 校验逻辑
- ❌ 用 `-k "not ..."` 临时跳过失败用例
- ❌ 在发送端测试中导入真实 Pillow（破坏零安装目标）

---

**文档维护**：新增测试用例时，按 `TC-<MODULE>-<NNN>` 规则续编，并在本文件对应章节追加条目；同时在「附录 A」更新统计数据。
