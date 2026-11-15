export async function recordSkillCopy(slug: string): Promise<boolean> {
  try {
    const response = await fetch("/api/v1/skills/" + encodeURIComponent(slug) + "/copy", {
      method: "POST",
    });
    return response.ok;
  } catch {
    return false;
  }
}
