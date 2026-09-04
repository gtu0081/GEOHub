import { useEffect, useState } from "react";
import {
  BlockStack,
  FormLayout,
  Modal,
  Select,
  Text,
  TextField,
} from "@shopify/polaris";

interface DiscoverModalProps {
  open: boolean;
  defaultBrand: string;
  submitting: boolean;
  onClose: () => void;
  onSubmit: (values: {
    subject: string;
    brand: string;
    seedQueries: string[];
    locale: string;
  }) => void;
}

/**
 * Polaris modal form for generating an AI question map (geo-discover).
 * Mirrors DiagnosisModal's structure so both flows feel identical.
 */
export function DiscoverModal({
  open,
  defaultBrand,
  submitting,
  onClose,
  onSubmit,
}: DiscoverModalProps) {
  const [subject, setSubject] = useState("");
  const [brand, setBrand] = useState(defaultBrand);
  const [seedQueries, setSeedQueries] = useState("");
  const [locale, setLocale] = useState("en-US");
  const [localeTouched, setLocaleTouched] = useState(false);

  useEffect(() => {
    if (defaultBrand) setBrand((current) => current || defaultBrand);
  }, [defaultBrand]);

  const parsedSeeds = seedQueries
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
  const valid = subject.trim().length > 0 && parsedSeeds.length >= 1;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="New question map"
      primaryAction={{
        content: "Generate question map",
        loading: submitting,
        disabled: !valid,
        onAction: () =>
          onSubmit({
            subject: subject.trim(),
            brand: brand.trim(),
            seedQueries: parsedSeeds,
            locale: localeTouched ? locale : "en-US",
          }),
      }}
      secondaryActions={[{ content: "Cancel", onAction: onClose }]}
    >
      <Modal.Section>
        <BlockStack gap="300">
          <Text as="p" variant="bodyMd" tone="subdued">
            We expand your seed questions into a deterministic map of what buyers
            ask AI assistants about this subject, then rank the content
            opportunities. Runs fully offline — usually finishes in seconds.
          </Text>
          <FormLayout>
            <TextField
              label="Subject"
              value={subject}
              onChange={setSubject}
              autoComplete="off"
              placeholder="e.g. specialty coffee beans"
              helpText="The category or topic buyers ask about."
            />
            <TextField
              label="Brand"
              value={brand}
              onChange={setBrand}
              autoComplete="off"
              placeholder="Your brand name"
              helpText="Prefilled from your shop — used to spot brand-specific questions."
            />
            <TextField
              label="Seed questions"
              value={seedQueries}
              onChange={setSeedQueries}
              autoComplete="off"
              multiline={5}
              placeholder={
                "what is the difference between arabica and robusta\nhow to store coffee beans\nbest coffee beans for espresso"
              }
              helpText={`One question per line (${parsedSeeds.length} entered, at least 1).`}
            />
            <Select
              label="Language"
              options={[
                { label: "English", value: "en-US" },
                { label: "中文", value: "zh-CN" },
              ]}
              value={locale}
              onChange={(value) => {
                setLocale(value);
                setLocaleTouched(true);
              }}
            />
          </FormLayout>
        </BlockStack>
      </Modal.Section>
    </Modal>
  );
}
