from pathlib import Path
R=Path(__file__).resolve().parents[1]
s=(R/'fac_tinyagent/p6_e3_train_attempt2.py').read_text()
s=s.replace('require_prefix_reuse: bool = False\n', 'require_prefix_reuse: bool = False,\n                       additional_train_paths: Optional[Mapping[str, str]] = None\n')
s=s.replace('now_iso, set_seed, sha256_file, write_json)', 'now_iso, set_seed, sha256_file, write_json, read_json)')
needle='    training_rows = new_rows + [r for rows in old_rows.values() for r in rows]'
s=s.replace(needle,"    # P8: additional candidates are available only for explicit post-midpoint plan items.\n    for family, path in (additional_train_paths or {}).items():\n        old_rows[family] += _load_checked_rows(path, family, 'P8 additional replay')\n"+needle)
s=s.replace('        counters.update(restored["counters"])', '''        assert restored['counters']['replay_samples'] == 0, 'P8 extension requires replay-free common prefix'
        from . import p7_fullstate_v2_20261115 as FS
        state = FS.capture(model, optimizer, scaler)
        receipt = FS.save(state, output / 'prefix_full_state.pt')
        FS.restore(FS.load(output / 'prefix_full_state.pt', receipt), model, optimizer, scaler)
        write_json(output / 'prefix_full_state_receipt.json', receipt)
        counters.update(restored["counters"])''')
s=s.replace('"old_data_sha256": {f: sha256_file(p) for f, p in old_train_paths.items()},','"old_data_sha256": {f: sha256_file(p) for f, p in old_train_paths.items()},\n        "p8_additional_replay_sha256": {f: sha256_file(p) for f,p in (additional_train_paths or {}).items()},')
s=s.replace('    model.save_pretrained(str(output))', '''    final_state = FS.capture(model, optimizer, scaler)
    final_receipt = FS.save(final_state, output / 'full_state.pt')
    FS.restore(FS.load(output / 'full_state.pt', final_receipt), model, optimizer, scaler)
    write_json(output / 'full_state_receipt.json', final_receipt)
    model.save_pretrained(str(output))''')
assert 'additional_train_paths:' in s and 'prefix_full_state.pt' in s
(R/'fac_tinyagent/p8_train_20261115.py').write_text(s)
print('P8 trainer additive copy generated: native prefix metadata unchanged, extra pools post-prefix only, exact full state and actual step receipts')
