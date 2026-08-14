"""sqr.receiver.decoder 单元测试。

覆盖：decode_qr_multi（多码解码，网格模式用）+ decode_qr 向后兼容。
pyzbar/opencv 通过 mock 注入，不依赖真实图像，保证测试确定性。
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from sqr.receiver.decoder import decode_qr, decode_qr_multi


class TestDecodeQrMulti:
    def test_returns_list_type(self):
        with patch("sqr.receiver.decoder._decode_multi_pyzbar", return_value=["a"]):
            result = decode_qr_multi(MagicMock())
        assert isinstance(result, list)

    def test_multiple_results_preserved_in_order(self):
        data = [
            "SQ1|abc123def456|1|3|0a1b2c3d|p1",
            "SQ1|abc123def456|2|3|0a1b2c3d|p2",
            "SQ1|abc123def456|3|3|0a1b2c3d|p3",
        ]
        with patch("sqr.receiver.decoder._decode_multi_pyzbar", return_value=data):
            result = decode_qr_multi(MagicMock())
        assert result == data
        assert len(result) == 3

    def test_empty_when_both_backends_empty(self):
        with patch("sqr.receiver.decoder._decode_multi_pyzbar", return_value=[]), \
             patch("sqr.receiver.decoder._decode_multi_opencv", return_value=[]):
            result = decode_qr_multi(MagicMock())
        assert result == []

    def test_falls_back_to_opencv_when_pyzbar_empty(self):
        opencv_data = ["from-opencv-1", "from-opencv-2"]
        with patch("sqr.receiver.decoder._decode_multi_pyzbar", return_value=[]), \
             patch("sqr.receiver.decoder._decode_multi_opencv", return_value=opencv_data):
            result = decode_qr_multi(MagicMock())
        assert result == opencv_data

    def test_pyzbar_nonempty_skips_opencv(self):
        with patch("sqr.receiver.decoder._decode_multi_pyzbar", return_value=["x"]) as mock_pyz, \
             patch("sqr.receiver.decoder._decode_multi_opencv",
                   return_value=["should-not-appear"]) as mock_cv:
            result = decode_qr_multi(MagicMock())
        assert result == ["x"]
        mock_pyz.assert_called_once()
        mock_cv.assert_not_called()

    def test_single_result_returns_one_element_list(self):
        with patch("sqr.receiver.decoder._decode_multi_pyzbar", return_value=["only"]):
            result = decode_qr_multi(MagicMock())
        assert result == ["only"]


class TestDecodeMultiPyzbarIntegration:
    def test_extracts_all_data_fields_in_order(self):
        from sqr.receiver.decoder import _decode_multi_pyzbar
        fake_results = [
            MagicMock(data=b"first"),
            MagicMock(data=b"second"),
            MagicMock(data=b"third"),
        ]
        with patch("pyzbar.pyzbar.decode", return_value=fake_results):
            out = _decode_multi_pyzbar(MagicMock())
        assert out == ["first", "second", "third"]

    def test_handles_str_data_defensively(self):
        from sqr.receiver.decoder import _decode_multi_pyzbar
        fake_results = [MagicMock(data="already-str")]
        with patch("pyzbar.pyzbar.decode", return_value=fake_results):
            out = _decode_multi_pyzbar(MagicMock())
        assert out == ["already-str"]

    def test_empty_results_returns_empty_list(self):
        from sqr.receiver.decoder import _decode_multi_pyzbar
        with patch("pyzbar.pyzbar.decode", return_value=[]):
            out = _decode_multi_pyzbar(MagicMock())
        assert out == []


class TestDecodeQrBackwardCompat:
    def test_returns_first_as_string(self):
        with patch("sqr.receiver.decoder._decode_with_pyzbar", return_value="hello"):
            result = decode_qr(MagicMock())
        assert result == "hello"
        assert isinstance(result, str)

    def test_returns_none_when_no_qr(self):
        with patch("sqr.receiver.decoder._decode_with_pyzbar", return_value=None), \
             patch("sqr.receiver.decoder._decode_with_opencv", return_value=None):
            result = decode_qr(MagicMock())
        assert result is None

    def test_falls_back_to_opencv_single(self):
        with patch("sqr.receiver.decoder._decode_with_pyzbar", return_value=None), \
             patch("sqr.receiver.decoder._decode_with_opencv", return_value="from-cv"):
            result = decode_qr(MagicMock())
        assert result == "from-cv"
