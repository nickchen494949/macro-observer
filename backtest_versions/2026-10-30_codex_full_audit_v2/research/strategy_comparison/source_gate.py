"""Source identity gate, deliberately independent of retrospective opt-in."""

def require_verified_index_eps():
    raise SystemExit(
        'BLOCK_SOURCE_IDENTITY: no verified direct Nasdaq-100 aggregate EPS series '
        'with historical availability/vintages is supplied. Some legacy entries '
        'read SP500_EPS.json; the LSEG export does not establish index identity. '
        '--revised-history cannot waive this gate. No EPS model was run.'
    )
