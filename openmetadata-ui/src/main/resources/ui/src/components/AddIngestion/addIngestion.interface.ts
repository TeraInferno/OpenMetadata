/*
 *  Copyright 2021 Collate
 *  Licensed under the Apache License, Version 2.0 (the "License");
 *  you may not use this file except in compliance with the License.
 *  You may obtain a copy of the License at
 *  http://www.apache.org/licenses/LICENSE-2.0
 *  Unless required by applicable law or agreed to in writing, software
 *  distributed under the License is distributed on an "AS IS" BASIS,
 *  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 *  See the License for the specific language governing permissions and
 *  limitations under the License.
 */

import { FilterPatternEnum } from '../../enums/filterPattern.enum';
import { FormSubmitType } from '../../enums/form.enum';
import { ServiceCategory } from '../../enums/service.enum';
import { CreateIngestionPipeline } from '../../generated/api/services/ingestionPipelines/createIngestionPipeline';
import {
  FilterPattern,
  IngestionPipeline,
  PipelineType,
} from '../../generated/entity/services/ingestionPipelines/ingestionPipeline';
import { DataObj } from '../../interface/service.interface';

export interface AddIngestionProps {
  pipelineType: PipelineType;
  heading: string;
  status: FormSubmitType;
  data?: IngestionPipeline;
  serviceCategory: ServiceCategory;
  serviceData: DataObj;
  showSuccessScreen?: boolean;
  handleCancelClick: () => void;
  onAddIngestionSave: (ingestion: CreateIngestionPipeline) => Promise<void>;
  onUpdateIngestion?: (
    data: IngestionPipeline,
    oldData: IngestionPipeline,
    id: string,
    displayName: string,
    triggerIngestion?: boolean
  ) => Promise<void>;
  onSuccessSave?: () => void;
  handleViewServiceClick?: () => void;
}

export interface ConfigureIngestionProps {
  ingestionName: string;
  serviceCategory: ServiceCategory;
  dashboardFilterPattern: FilterPattern;
  schemaFilterPattern: FilterPattern;
  tableFilterPattern: FilterPattern;
  topicFilterPattern: FilterPattern;
  chartFilterPattern: FilterPattern;
  includeView: boolean;
  enableDataProfiler: boolean;
  ingestSampleData: boolean;
  showDashboardFilter: boolean;
  showSchemaFilter: boolean;
  showTableFilter: boolean;
  showTopicFilter: boolean;
  showChartFilter: boolean;
  handleIncludeView: () => void;
  handleEnableDataProfiler: () => void;
  handleIngestSampleData: () => void;
  getIncludeValue: (value: string[], type: FilterPatternEnum) => void;
  getExcludeValue: (value: string[], type: FilterPatternEnum) => void;
  handleShowFilter: (value: boolean, type: FilterPatternEnum) => void;
  onCancel: () => void;
  onNext: () => void;
}

export type ScheduleIntervalProps = {
  repeatFrequency: string;
  handleRepeatFrequencyChange: (value: string) => void;
  startDate: string;
  handleStartDateChange: (value: string) => void;
  endDate: string;
  handleEndDateChange: (value: string) => void;
  onBack: () => void;
  onDeloy: () => void;
};
