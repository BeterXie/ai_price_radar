from scripts.migrate_source_platform_16688_v11 import DDL


def test_source_platform_16688_v11_expands_both_source_constraints():
    assert "'woocommerce', '16688', 'schema_org'" in DDL
    assert DDL.count("DROP CONSTRAINT IF EXISTS") == 2
