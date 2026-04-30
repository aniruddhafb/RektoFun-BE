-- Migration: create_clan_members_table  
-- Description: Creates the clan_members table for clan membership management
-- Recommended over array approach because:
--   1. Easy atomic operations for join/leave (INSERT/DELETE vs array manipulation)
--   2. Fast indexed lookups for membership checks
--   3. Supports roles (Leader/Co-Leader/Member) and status (Online/Away/Offline)
--   4. Historical tracking of join dates
-- Run this in Supabase SQL Editor (Dashboard → SQL Editor → New Query)

-- Create clan_members table (with soft-delete for join/leave history)
CREATE TABLE IF NOT EXISTS public.clan_members (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    clan_id UUID NOT NULL REFERENCES public.clans(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'Member' CHECK (role IN ('Leader', 'Co-Leader', 'Member')),
    status TEXT NOT NULL DEFAULT 'Offline' CHECK (status IN ('Online', 'Away', 'Offline')),
    joined_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    left_at TIMESTAMP WITH TIME ZONE,  -- NULL = currently in clan, set when user leaves
    is_active BOOLEAN NOT NULL DEFAULT true,  -- TRUE = in clan, FALSE = left
    CONSTRAINT clan_members_pkey PRIMARY KEY (id),
    CONSTRAINT clan_members_unique UNIQUE (clan_id, user_id)
) TABLESPACE pg_default;

-- Create indexes for clan_members (fast membership lookups)
CREATE INDEX IF NOT EXISTS idx_clan_members_clan_id ON public.clan_members USING btree (clan_id) TABLESPACE pg_default;
CREATE INDEX IF NOT EXISTS idx_clan_members_user_id ON public.clan_members USING btree (user_id) TABLESPACE pg_default;
CREATE INDEX IF NOT EXISTS idx_clan_members_clan_user ON public.clan_members USING btree (clan_id, user_id) TABLESPACE pg_default;

-- Partial unique index: ensures a user can only have ONE active membership per clan
-- (but can have multiple inactive rows as history)
CREATE UNIQUE INDEX idx_unique_active_membership
ON public.clan_members (clan_id, user_id)
WHERE is_active = true;

-- Enable RLS on clan_members
ALTER TABLE public.clan_members ENABLE ROW LEVEL SECURITY;

-- RLS Policies for clan_members
-- Anyone can read clan members (needed for UI to show member list)
CREATE POLICY "Clan members are publicly readable" ON public.clan_members
    FOR SELECT USING (true);

-- Leaders and Co-Leaders can manage members (kick, change role)
CREATE POLICY "Leaders can manage clan members" ON public.clan_members
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM public.clan_members cm
            WHERE cm.clan_id = clan_members.clan_id
            AND cm.user_id = auth.uid()
            AND cm.role IN ('Leader', 'Co-Leader')
        )
    );

-- Users can add themselves to clans
CREATE POLICY "Users can join clans" ON public.clan_members
    FOR INSERT WITH CHECK (
        user_id = auth.uid()
    );

-- Users can update their own membership (e.g., change status)
CREATE POLICY "Users can update own membership" ON public.clan_members
    FOR UPDATE USING (
        user_id = auth.uid()
    );

-- Users can leave clans (soft delete - sets left_at and is_active = false)
CREATE POLICY "Users can leave clans" ON public.clan_members
    FOR UPDATE USING (
        user_id = auth.uid()
    );


-- Now create clan_messages table (same as before)
CREATE TABLE IF NOT EXISTS public.clan_messages (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    clan_id UUID NOT NULL REFERENCES public.clans(id) ON DELETE CASCADE,
    sender_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    message TEXT NOT NULL CHECK (char_length(message) > 0 AND char_length(message) <= 2000),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT clan_messages_pkey PRIMARY KEY (id)
) TABLESPACE pg_default;

-- Create indexes for clan_messages
CREATE INDEX IF NOT EXISTS idx_clan_messages_clan_id ON public.clan_messages USING btree (clan_id) TABLESPACE pg_default;
CREATE INDEX IF NOT EXISTS idx_clan_messages_created_at ON public.clan_messages USING btree (created_at DESC) TABLESPACE pg_default;
CREATE INDEX IF NOT EXISTS idx_clan_messages_clan_created ON public.clan_messages USING btree (clan_id, created_at DESC) TABLESPACE pg_default;

-- Enable RLS on clan_messages
ALTER TABLE public.clan_messages ENABLE ROW LEVEL SECURITY;

-- RLS Policies for clan_messages (only active clan members can read/send)
CREATE POLICY "Only active clan members can read clan messages" ON public.clan_messages
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.clan_members cm
            WHERE cm.clan_id = clan_messages.clan_id
            AND cm.user_id = auth.uid()
            AND cm.is_active = true
        )
    );

CREATE POLICY "Only active clan members can send messages" ON public.clan_messages
    FOR INSERT WITH CHECK (
        sender_id = auth.uid()
        AND EXISTS (
            SELECT 1 FROM public.clan_members cm
            WHERE cm.clan_id = clan_messages.clan_id
            AND cm.user_id = auth.uid()
            AND cm.is_active = true
        )
    );

CREATE POLICY "Users can update own messages" ON public.clan_messages
    FOR UPDATE USING (sender_id = auth.uid());

CREATE POLICY "Users can delete own messages" ON public.clan_messages
    FOR DELETE USING (sender_id = auth.uid());
