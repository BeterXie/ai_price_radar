import { NextResponse } from "next/server";

export const dynamic = "force-static";
export const revalidate = 86400;

export function GET() {
  // The same contract covers two shapes: the full snapshot file and the small
  // latest.json pointer. They are separated with oneOf so a valid pointer
  // (which has no `products`) still validates.
  const schema = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://ai.pricememo.cn/price-radar-v1.schema.json",
    "title": "PriceRadarSnapshotFeed",
    "description": "Schema for AI Price Memory (PriceMemo) immutable snapshot feed and pointer.",
    "oneOf": [
      { "$ref": "#/$defs/SnapshotDocument" },
      { "$ref": "#/$defs/LatestPointer" }
    ],
    "$defs": {
      "SnapshotDocument": {
        "type": "object",
        "required": [
          "schema_version",
          "snapshot_id",
          "generated_at",
          "published_at",
          "stale",
          "ranking_policy_version",
          "product_count",
          "snapshot_url",
          "products"
        ],
        "properties": {
          "schema_version": { "type": "string", "enum": ["price-radar.v1"] },
          "snapshot_id": {
            "type": "string",
            "description": "Unique timestamped identifier of this catalog snapshot."
          },
          "generated_at": { "type": "string", "format": "date-time" },
          "published_at": { "type": "string", "format": "date-time" },
          "stale": {
            "type": "boolean",
            "description": "True if this snapshot data was generated more than 2 hours ago."
          },
          "ranking_policy_version": { "type": "string", "default": "available-non-shared-first.v1" },
          "snapshot_url": { "type": "string", "format": "uri" },
          "product_count": { "type": "integer", "minimum": 0 },
          "products": {
            "type": "array",
            "items": { "$ref": "#/$defs/ProductSnapshot" }
          }
        }
      },
      "LatestPointer": {
        "type": "object",
        "description": "latest.json pointer returned by /data/latest.json; it carries no product list.",
        "required": ["schema_version", "snapshot_id", "published_at", "snapshot_url", "product_count"],
        "properties": {
          "schema_version": { "type": "string", "enum": ["price-radar.v1"] },
          "snapshot_id": { "type": "string" },
          "generated_at": { "type": "string", "format": "date-time" },
          "published_at": { "type": "string", "format": "date-time" },
          "stale": { "type": "boolean" },
          "ranking_policy_version": { "type": "string" },
          "snapshot_url": { "type": "string", "format": "uri" },
          "product_count": { "type": "integer", "minimum": 0 }
        },
        "unevaluatedProperties": true
      },
      "ProductSnapshot": {
        "type": "object",
        "required": ["id", "slug", "display_name", "currency", "min_price", "offer_count", "in_stock_count", "top_5_offers"],
        "properties": {
          "id": { "type": "integer" },
          "slug": { "type": "string" },
          "display_name": { "type": "string" },
          "currency": { "type": "string", "default": "CNY" },
          "min_price": { "type": ["number", "null"] },
          "offer_count": { "type": "integer", "minimum": 0 },
          "in_stock_count": { "type": "integer", "minimum": 0 },
          "top_5_offers": {
            "type": "array",
            "items": { "$ref": "#/$defs/OfferItem" }
          }
        }
      },
      "OfferItem": {
        "type": "object",
        "required": ["id", "shop_token", "shop_name", "source_platform", "source_url", "price", "stock_status", "delivery_type", "warranty"],
        "properties": {
          "id": { "type": "integer" },
          "shop_token": { "type": "string" },
          "shop_name": { "type": "string" },
          "source_platform": { "type": "string" },
          "source_url": { "type": "string" },
          "original_name": { "type": "string" },
          "price": { "type": "number" },
          "currency": { "type": "string" },
          "stock_status": { "type": "string" },
          "stock_count": { "type": ["integer", "null"] },
          "delivery_type": { "type": "string" },
          "service_period": { "type": "string" },
          "warranty": { "type": "string" },
          "is_comparable": { "type": "boolean" },
          "is_trusted_price": { "type": "boolean" }
        }
      }
    }
  };

  return NextResponse.json(schema, {
    headers: {
      "Cache-Control": "public, max-age=86400",
      "Access-Control-Allow-Origin": "*",
    },
  });
}
