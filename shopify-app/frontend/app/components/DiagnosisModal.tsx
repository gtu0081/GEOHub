import { useEffect, useState } from "react";
import {
  BlockStack,
  Checkbox,
  FormLayout,
  Modal,
  Select,
  Text,
  TextField,
} from "@shopify/polaris";

interface DiagnosisModalProps {
  open: boolean;
  defaultUrl: string;
  submitting: boolean;
  onClose: () => void;
  onSubmit: (values: {
    targetUrl: string;
    locale: string;
    maxPages: number;
    demo: boolean;
  }) => void;
}

/**
 * Polaris modal form for starting a diagnosis run.
 */
export function DiagnosisModal({
  open,
  defaultUrl,
  submitting,
  onClose,
  onSubmit,
}: DiagnosisModalProps) {
  const [targetUrl, setTargetUrl] = useState(defaultUrl);
  const [locale, setLocale] = useState("en-US");
  const [maxPages, setMaxPages] = useState("10");
  const [demo, setDemo] = useState(false);

  // Loader data may arrive after first mount (or the shop query may return
  // late); backfill the suggestion without clobbering user edits.
  useEffect(() => {
    if (defaultUrl) setTargetUrl((current) => current || defaultUrl);
  }, [defaultUrl]);

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Run a diagnosis"
      primaryAction={{
        content: "Run diagnosis",
        loading: submitting,
        disabled: !targetUrl,
        onAction: () =>
          onSubmit({
            targetUrl: targetUrl.trim(),
            locale,
            maxPages: Math.min(10, Math.max(1, Number(maxPages) || 10)),
            demo,
          }),
      }}
      secondaryActions={[{ content: "Cancel", onAction: onClose }]}
    >
      <Modal.Section>
        <BlockStack gap="300">
          <Text as="p" variant="bodyMd" tone="subdued">
            We fetch up to ten representative pages from your storefront and score
            them across eight AI-search readiness dimensions. A run usually takes
            under two minutes.
          </Text>
          <FormLayout>
            <TextField
              label="Storefront URL"
              value={targetUrl}
              onChange={setTargetUrl}
              autoComplete="off"
              placeholder="https://your-store.com"
              helpText="Your primary storefront domain, prefilled from your shop settings."
            />
            <FormLayout.Group>
              <Select
                label="Report language"
                options={[
                  { label: "English", value: "en-US" },
                  { label: "中文", value: "zh-CN" },
                ]}
                value={locale}
                onChange={setLocale}
              />
              <TextField
                label="Pages to inspect"
                type="number"
                min={1}
                max={10}
                value={maxPages}
                onChange={setMaxPages}
                autoComplete="off"
              />
            </FormLayout.Group>
            <Checkbox
              label="Offline demo data"
              checked={demo}
              onChange={setDemo}
              helpText="Score a bundled sample store instead of your own pages."
            />
          </FormLayout>
        </BlockStack>
      </Modal.Section>
    </Modal>
  );
}
