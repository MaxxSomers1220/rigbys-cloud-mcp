-- Only references verified by the Gumroad adapter use this namespace.
-- Preserve legacy/synthetic references unchanged, including existing duplicates.
CREATE UNIQUE INDEX redemptions_verified_sale_ref_unique_idx
    ON redemptions(gumroad_sale_ref)
    WHERE starts_with(gumroad_sale_ref, 'gumroad:');
