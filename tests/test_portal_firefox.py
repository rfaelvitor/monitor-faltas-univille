from faltas.portal import decodificar_bytes
from faltas.portal_firefox import preparar_copia


def test_decodifica_cp1252():
    assert decodificar_bytes("Frequência".encode("cp1252"), "text/html; charset=ISO-8859-1") == "Frequência"


def test_copia_inteira_e_depois_so_cookies(tmp_path):
    origem, destino = tmp_path / "o", tmp_path / "d"
    (origem / "cache2").mkdir(parents=True)
    (origem / "prefs.js").write_text("a")
    (origem / "cookies.sqlite").write_text("1")
    (origem / "parent.lock").write_text("x")
    (origem / "cache2" / "lixo").write_text("x")
    preparar_copia(origem, destino)
    assert (destino / "prefs.js").exists() and not (destino / "cache2").exists() and not (destino / "parent.lock").exists()
    (origem / "prefs.js").write_text("b")
    (origem / "cookies.sqlite").write_text("2")
    preparar_copia(origem, destino)
    assert (destino / "prefs.js").read_text() == "a" and (destino / "cookies.sqlite").read_text() == "2"
