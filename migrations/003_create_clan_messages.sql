-- Migration: create_clan_messages_table
-- Description: Creates the clan_messages table for clan chat functionality
-- Assumes clans table already exists with a member_ids array column (UUID[])
-- Run this in Supabase SQL Editor (Dashboard → SQL Editor → New Query)

-- Create clan_messages table
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

-- RLS Policies for clan_messages (only clan members can read/send messages)
-- Uses the existing clans.member_ids array to check membership
CREATE POLICY "Only clan members can read clan messages" ON public.clan_messages
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.clans c
            WHERE c.id = clan_messages.clan_id
            AND clan_messages.sender_id = ANY(c.member_ids)
        )
    );

CREATE POLICY "Only clan members can send messages" ON public.clan_messages
    FOR INSERT WITH CHECK (
        sender_id = auth.uid()
        AND EXISTS (
            SELECT 1 FROM public.clans c
            WHERE c.id = clan_messages.clan_id
            AND auth.uid() = ANY(c.member_ids)
        )
    );

CREATE POLICY "Users can update own messages" ON public.clan_messages
    FOR UPDATE USING (sender_id = auth.uid());

CREATE POLICY "Users can delete own messages" ON public.clan_messages
    FOR DELETE USING (sender_id = auth.uid());
