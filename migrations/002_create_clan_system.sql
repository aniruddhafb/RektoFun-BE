-- Migration: create_clan_system
-- Description: Creates clans, clan_members, and clan_messages tables for clan chat functionality

-- Create clans table
CREATE TABLE IF NOT EXISTS public.clans (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    tagline TEXT NULL,
    description TEXT NULL,
    leader_wallet TEXT NULL,
    logo TEXT NULL,
    type TEXT NOT NULL DEFAULT 'Public' CHECK (type IN ('Public', 'Private', 'Invite Only')),
    max_members INTEGER NOT NULL DEFAULT 50,
    total_wins INTEGER NOT NULL DEFAULT 0,
    total_rekts INTEGER NOT NULL DEFAULT 0,
    win_rate NUMERIC NOT NULL DEFAULT 0,
    rekt_points TEXT NULL DEFAULT '0',
    verified BOOLEAN NOT NULL DEFAULT false,
    is_open_to_join BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT clans_pkey PRIMARY KEY (id)
) TABLESPACE pg_default;

-- Create indexes for clans
CREATE INDEX IF NOT EXISTS idx_clans_slug ON public.clans USING btree (slug) TABLESPACE pg_default;
CREATE INDEX IF NOT EXISTS idx_clans_name ON public.clans USING btree (name) TABLESPACE pg_default;

-- Create clan_members table
CREATE TABLE IF NOT EXISTS public.clan_members (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    clan_id UUID NOT NULL REFERENCES public.clans(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'Member' CHECK (role IN ('Leader', 'Co-Leader', 'Member')),
    status TEXT NOT NULL DEFAULT 'Offline' CHECK (status IN ('Online', 'Away', 'Offline')),
    joined_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT clan_members_pkey PRIMARY KEY (id),
    CONSTRAINT clan_members_unique UNIQUE (clan_id, user_id)
) TABLESPACE pg_default;

-- Create indexes for clan_members
CREATE INDEX IF NOT EXISTS idx_clan_members_clan_id ON public.clan_members USING btree (clan_id) TABLESPACE pg_default;
CREATE INDEX IF NOT EXISTS idx_clan_members_user_id ON public.clan_members USING btree (user_id) TABLESPACE pg_default;
CREATE INDEX IF NOT EXISTS idx_clan_members_clan_user ON public.clan_members USING btree (clan_id, user_id) TABLESPACE pg_default;

-- Create clan_messages table
CREATE TABLE IF NOT EXISTS public.clan_messages (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    clan_id UUID NOT NULL REFERENCES public.clans(id) ON DELETE CASCADE,
    sender_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT clan_messages_pkey PRIMARY KEY (id)
) TABLESPACE pg_default;

-- Create indexes for clan_messages
CREATE INDEX IF NOT EXISTS idx_clan_messages_clan_id ON public.clan_messages USING btree (clan_id) TABLESPACE pg_default;
CREATE INDEX IF NOT EXISTS idx_clan_messages_created_at ON public.clan_messages USING btree (created_at DESC) TABLESPACE pg_default;
CREATE INDEX IF NOT EXISTS idx_clan_messages_clan_created ON public.clan_messages USING btree (clan_id, created_at DESC) TABLESPACE pg_default;

-- Create trigger function to auto-update updated_at for clans
CREATE OR REPLACE FUNCTION update_clans_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for auto-updating updated_at on clans
DROP TRIGGER IF EXISTS update_clans_updated_at ON public.clans;
CREATE TRIGGER update_clans_updated_at
    BEFORE UPDATE ON public.clans
    FOR EACH ROW
    EXECUTE FUNCTION update_clans_updated_at_column();

-- Enable RLS on all clan tables
ALTER TABLE public.clans ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.clan_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.clan_messages ENABLE ROW LEVEL SECURITY;

-- RLS Policies for clans table
-- Policy: Anyone can read clans (public listing)
CREATE POLICY "Clans are publicly readable" ON public.clans
    FOR SELECT USING (true);

-- Policy: Anyone can create clans
CREATE POLICY "Clans can be created publicly" ON public.clans
    FOR INSERT WITH CHECK (true);

-- RLS Policies for clan_members table
-- Policy: Anyone can read clan members (needed to check membership)
CREATE POLICY "Clan members are publicly readable" ON public.clan_members
    FOR SELECT USING (true);

-- Policy: Clan leaders can manage members
CREATE POLICY "Leaders can manage clan members" ON public.clan_members
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM public.clan_members cm
            WHERE cm.clan_id = clan_members.clan_id
            AND cm.user_id = auth.uid()
            AND cm.role IN ('Leader', 'Co-Leader')
        )
    );

-- Policy: Users can add themselves to clans (for open clans)
CREATE POLICY "Users can join open clans" ON public.clan_members
    FOR INSERT WITH CHECK (
        user_id = auth.uid()
    );

-- Policy: Users can update their own membership
CREATE POLICY "Users can update own membership" ON public.clan_members
    FOR UPDATE USING (
        user_id = auth.uid()
    );

-- RLS Policies for clan_messages table
-- Policy: Only clan members can read clan messages
CREATE POLICY "Only clan members can read clan messages" ON public.clan_messages
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.clan_members cm
            WHERE cm.clan_id = clan_messages.clan_id
            AND cm.user_id = auth.uid()
        )
    );

-- Policy: Only clan members can send messages
CREATE POLICY "Only clan members can send messages" ON public.clan_messages
    FOR INSERT WITH CHECK (
        sender_id = auth.uid()
        AND EXISTS (
            SELECT 1 FROM public.clan_members cm
            WHERE cm.clan_id = clan_messages.clan_id
            AND cm.user_id = auth.uid()
        )
    );

-- Policy: Users can update their own messages
CREATE POLICY "Users can update own messages" ON public.clan_messages
    FOR UPDATE USING (
        sender_id = auth.uid()
    );

-- Policy: Users can delete their own messages
CREATE POLICY "Users can delete own messages" ON public.clan_messages
    FOR DELETE USING (
        sender_id = auth.uid()
    );

-- Insert some sample clans (for testing)
INSERT INTO public.clans (slug, name, tagline, description, type, max_members, total_wins, total_rekts, win_rate, rekt_points, verified, is_open_to_join)
VALUES 
    ('alpha-syndicate', 'Alpha Syndicate', 'Trade smart. Win together.', 'Always stay one step ahead of the market.', 'Public', 50, 128, 78, 78, '12.4K', true, true),
    ('rekt-hunters', 'Rekt Hunters', 'Hunt the markets. Rekt the rest.', 'For those who dare to challenge the market.', 'Invite Only', 50, 96, 45, 74, '9.8K', true, false),
    ('market-mavericks', 'Market Mavericks', 'Different mindset. Better results.', 'Where unconventional thinking meets profits.', 'Public', 50, 75, 31, 71, '8.2K', true, true)
ON CONFLICT (slug) DO NOTHING;
