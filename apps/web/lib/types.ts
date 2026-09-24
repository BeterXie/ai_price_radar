export type OfficialPriceReference = {
  provider: string;
  plan: string;
  price: string | null;
  currency: string;
  billing_period: string;
  url: string;
  checked_at: string;
  note: string;
};

export type SourceHealth = {
  score: number;
  label: string;
  reasons: string[];
};

export type PriceTrendPoint = {
  bucket_at: string;
  price_currency: string;
  trusted_lowest_price: string | null;
  median_price: string | null;
  in_stock_count: number;
  observation_count: number;
};

export type ProductCard = {
  slug: string;
  platform: string;
  brand: string;
  display_name: string;
  subtitle: string;
  product_type: string;
  price_currency: string;
  lowest_price: string | null;
  related_lowest_price: string | null;
  offer_count: number;
  in_stock_count: number;
  comparable_offer_count: number;
  trusted_offer_count: number;
  median_price: string | null;
  source_count: number;
  data_quality_score: number;
  data_quality_label: string;
  official_reference: OfficialPriceReference | null;
  last_updated_at: string | null;
  tags: string[];
};

export type Offer = {
  id: number;
  shop_token: string;
  shop_name: string;
  source_platform: string;
  source_platform_label: string;
  source_kind: string;
  source_kind_label: string;
  original_name: string;
  original_category: string;
  original_description: string;
  description_available: boolean;
  goods_type: string;
  price: string | null;
  market_price: string | null;
  currency: string;
  stock_count: number | null;
  stock_status: string;
  auto_delivery: boolean | null;
  tags: string[];
  risk_flags: string[];
  delivery_type: string;
  is_comparable: boolean;
  service_period: string;
  warranty: string;
  use_scenarios: string[];
  item_fingerprint: string;
  low_price_warning: string | null;
  is_trusted_price: boolean;
  source_health: SourceHealth;
  source_url: string;
  click_count?: number;
  first_seen_at: string;
  last_seen_at: string;
  observed_at: string;
};

export type ProductDetail = ProductCard & {
  description: string;
  highest_price: string | null;
  offer_group_count: number;
  price_breakdown: DeliveryPriceSummary[];
  snapshot_id: number | null;
  snapshot_at: string | null;
  offers: Offer[];
  offer_groups: OfferGroup[];
  history: { observed_at: string; price: string | null; currency: string; stock_status: string }[];
  trend: PriceTrendPoint[];
};

export type ProductHistory = {
  trend: PriceTrendPoint[];
};

export type DeliveryPriceSummary = {
  delivery_type: string;
  price_currency: string;
  lowest_price: string | null;
  offer_count: number;
  in_stock_count: number;
};

export type OfferGroup = {
  product_slug: string;
  product_name: string;
  fingerprint: string;
  representative: Offer;
  offer_count: number;
  shop_count: number;
  in_stock_count: number;
  price_currency: string;
  lowest_price: string | null;
  highest_price: string | null;
  click_count?: number;
  latest_observed_at: string | null;
};

export type OfferPage = {
  items: Offer[];
};

export type OfferGroupPage = {
  items: OfferGroup[];
  total: number;
  offer_total: number;
  snapshot_id: number | null;
};

export type CatalogOfferGroupPage = OfferGroupPage & {
  in_stock_count: number;
  comparable_offer_count: number;
  trusted_offer_count: number;
  metrics_note: string;
  last_updated_at: string | null;
  snapshot_at: string | null;
};

export type GroupOffers = {
  items: Offer[];
};

export type ShopDetail = {
  token: string;
  name: string;
  source_url: string;
  platform: string;
  source_platform: string;
  source_platform_label: string;
  source_kind: string;
  source_kind_label: string;
  status: string;
  first_seen_at: string;
  last_success_at: string | null;
  last_seen_at: string | null;
  consecutive_failures: number;
  source_health: SourceHealth;
  offer_count: number;
  today_clicks?: number;
  total_clicks?: number;
  products: ShopProduct[];
  offers: Offer[];
};

export type ShopProduct = {
  slug: string;
  display_name: string;
  offer_count: number;
  in_stock_count: number;
};

export type ShopCard = {
  token: string;
  name: string;
  source_url: string;
  source_platform: string;
  source_platform_label: string;
  offer_count: number;
  in_stock_count: number;
  product_count: number;
  first_seen_at: string;
  last_seen_at: string | null;
  last_success_at: string | null;
  product_slugs: string[];
};

export type ShopListResponse = {
  items: ShopCard[];
  total: number;
};

export type SiteNotice = {
  enabled: boolean;
  badge: string;
  title: string;
  content: string;
  link_text?: string;
  link_url?: string;
};

export type CommunityNotice = {
  enabled: boolean;
  title: string;
  desc: string;
  qq_group: string;
  qq_url?: string;
  btn_text: string;
};

export type Meta = {
  platforms: string[];
  brands: string[];
  source_platforms: { id: string; label: string }[];
  product_types: string[];
  tags: string[];
  advertise_enabled?: boolean;
  ad_slots_enabled?: boolean;
  relay_hub_enabled?: boolean;
  relay_station_count?: number;
  bot_enabled?: boolean;
  site_notice?: SiteNotice | null;
  community_notice?: CommunityNotice | null;
};

export const AD_PLACEMENTS = ["home_hero", "catalog_top", "product_offers", "relay_hub", "sidebar"] as const;
export type AdPlacement = (typeof AD_PLACEMENTS)[number];

export type AdSlotPublic = {
  id: number;
  placement: AdPlacement | string;
  title: string;
  description: string;
  sponsor_name: string;
  badge: string;
  cta_text: string;
  link_url: string;
  image_url: string;
};

export type AdSlotListOut = {
  items: AdSlotPublic[];
  enabled: boolean;
};

export type AdSlotAdmin = AdSlotPublic & {
  sort_order: number;
  is_enabled: boolean;
  starts_at: string | null;
  ends_at: string | null;
  click_count: number;
  created_at: string | null;
  updated_at: string | null;
};

export type AdSlotInput = {
  placement: AdPlacement;
  title: string;
  description: string;
  sponsor_name: string;
  badge: string;
  cta_text: string;
  link_url: string;
  image_url: string;
  sort_order: number;
  is_enabled: boolean;
  starts_at: string | null;
  ends_at: string | null;
};

export type RelayStationPublic = {
  id: number;
  name: string;
  url: string;
  tagline: string;
  description: string;
  supported_models: string[];
  price_note: string;
  billing_note: string;
  tags: string[];
  is_sponsored: boolean;
  click_count: number;
  updated_at: string | null;
};

export type RelayStationListOut = {
  items: RelayStationPublic[];
  total: number;
  enabled: boolean;
};

export type RelayStationAdmin = RelayStationPublic & {
  is_enabled: boolean;
  sort_order: number;
  created_at: string | null;
};

export type RelayStationInput = {
  name: string;
  url: string;
  tagline: string;
  description: string;
  supported_models: string[];
  price_note: string;
  billing_note: string;
  tags: string[];
  is_sponsored: boolean;
  is_enabled: boolean;
  sort_order: number;
};

export type CatalogResponse = {
  items: ProductCard[];
  total: number;
  offer_count: number;
  in_stock_count: number;
  comparable_offer_count: number;
  trusted_offer_count: number;
  metrics_note: string;
  snapshot_id: number | null;
  snapshot_at: string | null;
};

export type PublicCorrection = {
  id: number;
  offer_id: number | null;
  kind: string;
  public_summary: string;
  merchant_response: string;
  resolved_at: string | null;
  created_at: string;
};

export type PublicCorrectionPage = {
  items: PublicCorrection[];
  total: number;
};

export type RelatedProductSummary = {
  slug: string;
  platform: string;
  display_name: string;
  subtitle: string;
  product_type: string;
};

export type CommunitySkillSummary = {
  id: number;
  slug: string;
  kind: "benchmark" | "skill" | "article" | string;
  title: string;
  subtitle: string;
  summary: string;
  author_name: string;
  author_url: string;
  repo_url: string;
  stars_count: number;
  install_command: string;
  prompt_template: string;
  demo_url: string;
  demo_type: "none" | "pelican_arena" | "iframe" | string;

  tags: string[];
  target_models: string[];
  related_product_slug: string | null;
  is_pinned: boolean;
  is_visible: boolean;
  sort_order: number;
  view_count: number;
  copy_count: number;
  created_at: string;
  updated_at: string;
};

export type CommunitySkillDetail = CommunitySkillSummary & {
  content_markdown: string;
  prompt_template: string;
  related_product: RelatedProductSummary | null;
};

export type CommunitySkillPage = {
  items: CommunitySkillSummary[];
  total: number;
  page: number;
  page_size: number;
  kinds: string[];
  all_tags: string[];
};

export type AdminCommunitySkillCreate = {
  slug: string;
  kind: string;
  title: string;
  subtitle?: string;
  summary?: string;
  content_markdown?: string;
  prompt_template?: string;
  author_name?: string;
  author_url?: string;
  repo_url?: string;
  stars_count?: number;
  install_command?: string;
  demo_url?: string;
  demo_type?: string;
  tags?: string[];
  target_models?: string[];
  related_product_slug?: string | null;
  is_pinned?: boolean;
  is_visible?: boolean;
  sort_order?: number;
};

export type AdminCommunitySkillUpdate = Partial<AdminCommunitySkillCreate>;

export type User = {
  id: number;
  email: string | null;
  nickname: string;
  avatar_url: string;
  has_qq_bound: boolean;
  has_password?: boolean;
  created_at: string;
};

export type AuthSessionState = {
  authenticated: boolean;
  user: User | null;
};

export type UserBotBinding = {
  id: number;
  channel: string;
  target_id: string;
  is_active: boolean;
  notify_price_drop: boolean;
  notify_price_hike: boolean;
  created_at: string;
};

export type UserProfileResponse = {
  user: User;
  qq_bot_binding: UserBotBinding | null;
  bot_enabled?: boolean;
};

export type QQBotBindingStartResponse = {
  session_id: string;
  bind_code: string;
  qrcode_url?: string;
  expires_in_seconds: number;
  instruction: string;
};

export type ShopCoupon = {
  id: number;
  name: string;
  code: string;
  discount_amount: number | string;
  min_spend: number | string;
  shop_id?: number | null;
  shop_name: string;
  shop_url: string;
  is_assigned: boolean;
  assigned_at?: string | null;
  expires_at: string;
  is_used: boolean;
  created_at: string;
  coupon_batch_id?: number;
  campaign_id?: number | null;
};

export type UserCouponListOut = {
  items: ShopCoupon[];
  count: number;
};

export type CouponClaimResponse = {
  success: boolean;
  message: string;
  coupon?: ShopCoupon | null;
};

export type CouponDropStatus = {
  enabled: boolean;
  probability: number;
  has_stock: boolean;
  remaining_stock: number;
};

export type AdminCouponStats = {
  total_coupons: number;
  assigned_coupons: number;
  unassigned_coupons: number;
  used_coupons: number;
  total_campaigns: number;
  drop_enabled: boolean;
  drop_probability: number;
  dynamic_drop: boolean;
  daily_drop_limit: number;
  drop_trigger_count: number;
};

export type AdminCouponSettingsUpdate = {
  drop_enabled?: boolean;
  drop_probability?: number;
  dynamic_drop?: boolean;
  daily_drop_limit?: number;
};

export type AdminCouponImportRequest = {
  name: string;
  discount_amount: number;
  min_spend: number;
  expires_at?: string | null;
  shop_id?: number | null;
  shop_name: string;
  shop_url: string;
  coupon_batch_id: number;
  codes_text: string;
};

export type AdminCouponImportResponse = {
  success: boolean;
  imported_count: number;
  skipped_count: number;
  message: string;
};

export type AdminCouponPageOut = {
  items: ShopCoupon[];
  total: number;
  page: number;
  page_size: number;
};

export type CampaignRead = {
  id: number;
  campaign_code: string;
  title: string;
  coupon_batch_id: number;
  shop_id?: number | null;
  shop_url?: string | null;
  shop_name?: string | null;
  max_per_user: number;
  total_quota: number;
  claimed_count: number;
  is_active: boolean;
  expires_at: string;
  created_at: string;
};

export type AdminCampaignCreate = {
  campaign_code: string;
  title: string;
  coupon_batch_id: number;
  shop_id?: number | null;
  shop_url?: string | null;
  shop_name?: string | null;
  max_per_user: number;
  total_quota: number;
  expires_at?: string | null;
};

export type AdminUserItem = {
  id: number;
  email: string | null;
  nickname: string;
  avatar_url: string;
  has_qq_bound: boolean;
  has_bot_bound: boolean;
  bot_channel: string | null;
  bot_target_id: string | null;
  bot_active: boolean;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
  last_login_ip: string;
  last_active_at: string | null;
  session_duration_seconds: number;
  total_duration_seconds: number;
  is_online: boolean;
  button_click_count: number;
  coupon_count: number;
  active_coupon_count: number;
  used_coupon_count: number;
};

export type AdminUserPageOut = {
  items: AdminUserItem[];
  total: number;
  page: number;
  limit: number;
};

export type AdminUserStatsOut = {
  total_users: number;
  active_today: number;
  active_7d: number;
  online_now: number;
  total_clicks: number;
  total_coupons_held: number;
};

export type AdminUserSessionItem = {
  token: string;
  ip_address: string;
  user_agent: string;
  created_at: string;
  last_active_at: string | null;
  duration_seconds: number;
  is_active: boolean;
};

export type AdminUserActionLogItem = {
  id: number;
  action_type: string;
  action_name: string;
  target_id: string;
  page: string;
  ip_address: string;
  extra_data: Record<string, unknown>;
  created_at: string;
};

export type AdminUserDetailOut = {
  user: AdminUserItem;
  sessions: AdminUserSessionItem[];
  coupons: ShopCoupon[];
  action_logs: AdminUserActionLogItem[];
  bot_bindings: UserBotBinding[];
  subscription_count: number;
};

export type AdminBroadcastAudienceOut = {
  total_users: number;
  email_users: number;
  bot_users: number;
  total_reach: number;
};

export type AdminBroadcastCreate = {
  operation_key: string;
  title: string;
  content: string;
  channels: string[];
};

export type AdminBroadcastItem = {
  id: number;
  operation_key: string;
  title: string;
  content: string;
  channels: string[];
  target_user_count: number;
  email_sent_count: number;
  bot_sent_count: number;
  status: string;
  created_by: string;
  created_at: string;
};



