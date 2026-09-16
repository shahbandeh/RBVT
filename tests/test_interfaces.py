import shlex
import pytest
from rbvt.cli import build_parser
from rbvt.interface import BackgroundRequest, export_products


def test_equivalent_cli():
    request = BackgroundRequest('12:00:00', '-10:30:00', target_name="Target 'A'")
    args = build_parser().parse_args(shlex.split(request.command(12))[1:])
    assert args.ra == request.longitude
    assert args.dec == request.latitude
    assert args.target_name == request.target_name
    assert args.day == 12


@pytest.mark.parametrize('changes', [{'threshold': 'nan'}, {'threshold': '.5'},
    {'wavelength': 'inf', 'optical_element': 'Custom wavelength'}, {'latitude': '91'},
    {'coordinate_system': 'unknown'}, {'optical_element': 'unknown'}])
def test_invalid_requests(changes):
    with pytest.raises(ValueError):
        BackgroundRequest(**changes).parameters()


def test_ui_exports_match_model(offline):
    request = BackgroundRequest(target_name='<test>')
    result = request.calculate()
    day = int(result.bkg_data['calendar'][0])
    exports = export_products(result, day, request.target_name)
    assert exports['background.png'].startswith(b'\x89PNG')
    assert b'&lt;test&gt;' in exports['report.html']
    assert b'data:image/png;base64,' in exports['report.html']
    assert b'total_MJy_sr' in exports['daily.csv']
    assert b'wavelength_um' in exports['spectrum.csv']
