"use client";

let activeOwner: string | null = null;

export function tryAcquireGlobalOverlay(owner: string): boolean {
  if (activeOwner && activeOwner !== owner) return false;
  activeOwner = owner;
  return true;
}

export function releaseGlobalOverlay(owner: string): void {
  if (activeOwner === owner) activeOwner = null;
}
