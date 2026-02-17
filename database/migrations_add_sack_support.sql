-- Migration SQL for existing lmj_pos.db to support per-sack sales
ALTER TABLE inventory ADD COLUMN sack_size REAL;
ALTER TABLE inventory ADD COLUMN sack_price REAL;
ALTER TABLE sales ADD COLUMN sale_type TEXT; -- 'kilo' or 'sack'
ALTER TABLE sales ADD COLUMN sack_size REAL;
ALTER TABLE sales ADD COLUMN unit_price REAL;
