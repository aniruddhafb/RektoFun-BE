ALTER TABLE public.challenges
ADD COLUMN IF NOT EXISTS asset_name text;
