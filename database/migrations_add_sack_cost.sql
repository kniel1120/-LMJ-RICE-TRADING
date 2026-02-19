-- Migration: Add sack_cost column to sales table for correct cost tracking of sack sales
ALTER TABLE sales ADD COLUMN sack_cost REAL;