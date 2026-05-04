-- Migration: Add corrected transcript column to audio_records
-- Run this against your existing MySQL database to add the new column.

ALTER TABLE audio_records
ADD COLUMN transcript_corrected_encrypted TEXT DEFAULT NULL
AFTER transcript_encrypted;
