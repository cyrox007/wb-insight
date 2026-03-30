<script setup>
import { computed, ref } from 'vue';

const props = defineProps({
    data: {
        type: Array,
        default: () => []
    },
    isLoading: {
        default: false,
        type: Boolean
    },
    title: {
        type: String,
        default: 'Продажи по категориям'
    },
});

const highlightedIndex = ref(-1);

const colors = [
    '#FFB300',
    '#E74C3C',
    '#3498DB',
    '#2ECC71',
    '#FF6B35',
    '#9B59B6',
    '#1ABC9C',
    '#F39C12'
];

const hasData = computed(() => {
    return props.data && props.data.length > 0;
});

const chartData = computed(() => {
    if (!hasData.value) return [];
    const total = props.data.reduce((sum, item) => sum + (item.value || 0), 0);
    return props.data.map(item => ({
        category: item.category,
        value: item.value || 0,
        percent: total > 0 ? ((item.value || 0) / total * 100).toFixed(1) : 0
    }));
});

const total = computed(() => {
    return chartData.value.reduce((sum, item) => sum + item.value, 0);
});

const getColor = (index) => {
    return colors[index % colors.length];
};

const formatPrice = (value) => {
    if (!value && value !== 0) return '0 ₽';
    return value.toLocaleString('ru-RU') + ' ₽';
};

const formatShortPrice = (value) => {
    if (value >= 1000000) {
        return (value / 1000000).toFixed(1) + ' млн';
    } else if (value >= 1000) {
        return (value / 1000).toFixed(0) + ' тыс';
    }
    return value.toString();
};

const segments = computed(() => {
    if (!hasData.value) return [];

    let currentAngle = -90;
    const radius = 18;
    const innerRadius = 12;
    const centerX = 25;
    const centerY = 25;

    return chartData.value.map(item => {
        const angle = (item.percent / 100) * 360;
        const startAngle = currentAngle;
        const endAngle = currentAngle + angle;

        const startRad = (startAngle * Math.PI) / 180;
        const endRad = (endAngle * Math.PI) / 180;

        const x1 = centerX + radius * Math.cos(startRad);
        const y1 = centerY + radius * Math.sin(startRad);
        const x2 = centerX + radius * Math.cos(endRad);
        const y2 = centerY + radius * Math.sin(endRad);

        const x3 = centerX + innerRadius * Math.cos(endRad);
        const y3 = centerY + innerRadius * Math.sin(endRad);
        const x4 = centerX + innerRadius * Math.cos(startRad);
        const y4 = centerY + innerRadius * Math.sin(startRad);

        const largeArcFlag = angle > 180 ? 1 : 0;

        const path = [
            `M ${x1} ${y1}`,
            `A ${radius} ${radius} 0 ${largeArcFlag} 1 ${x2} ${y2}`,
            `L ${x3} ${y3}`,
            `A ${innerRadius} ${innerRadius} 0 ${largeArcFlag} 0 ${x4} ${y4}`,
            'Z'
        ].join(' ');

        currentAngle = endAngle;

        return { path, percent: item.percent, value: item.value, category: item.category };
    });
});

const highlightSegment = (index) => {
    highlightedIndex.value = index;
};

const resetHighlight = () => {
    highlightedIndex.value = -1;
};
</script>

<template>
    <div class="donut-chart">
        <h3 class="chart-title">{{ title }}</h3>

        <div v-if="isLoading" class="chart-loading">
            <div class="loading-spinner"></div>
            <p class="loading-text">Загрузка данных...</p>
        </div>

        <div v-else-if="!hasData" class="chart-empty">
            <div class="empty-icon">📊</div>
            <p class="empty-text">Нет данных для отображения</p>
            <p class="empty-hint">Данные появятся после синхронизации</p>
        </div>

        <div v-else class="chart-content">
            <div class="chart-wrapper">
                <svg viewBox="0 0 50 50" class="chart">
                    <g v-for="(segment, index) in segments" :key="index">
                        <path :d="segment.path" :fill="getColor(index)" class="chart-segment"
                            :class="{ 'highlighted': highlightedIndex === index }" @mouseenter="highlightSegment(index)"
                            @mouseleave="resetHighlight" />
                    </g>
                    <!-- Center circle -->
                    <circle cx="25" cy="25" r="12" fill="var(--card-bg)" />
                    <!-- Total - ИСПРАВЛЕНО: правильное позиционирование -->
                    <text x="25" y="24" text-anchor="middle" class="center-total" dominant-baseline="middle">
                        {{ formatShortPrice(total) }}
                    </text>
                    <text x="25" y="30" text-anchor="middle" class="center-label" dominant-baseline="middle">
                        Всего
                    </text>
                </svg>
            </div>

            <div class="legend">
                <div v-for="(item, index) in chartData" :key="item.category" class="legend-item"
                    @mouseenter="highlightSegment(index)" @mouseleave="resetHighlight">
                    <span class="legend-color" :style="{ backgroundColor: getColor(index) }"></span>
                    <span class="legend-label">{{ item.category }}</span>
                    <span class="legend-value">{{ formatPrice(item.value) }}</span>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.donut-chart {
    padding: 16px;
    background: var(--card-bg);
    border-radius: 8px;
    border: 1px solid var(--border-color);
}

.chart-title {
    margin: 0 0 20px 0;
    font-size: 16px;
    font-weight: 600;
    color: var(--text-color);
}

.chart-loading,
.chart-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 40px 20px;
    text-align: center;
    color: var(--text-color);
}

.loading-spinner {
    width: 40px;
    height: 40px;
    border: 4px solid var(--border-color);
    border-top-color: var(--secondary-color);
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin-bottom: 15px;
}

@keyframes spin {
    to {
        transform: rotate(360deg);
    }
}

.loading-text {
    font-size: 14px;
    margin: 0;
}

.empty-icon {
    font-size: 48px;
    margin-bottom: 15px;
    opacity: 0.6;
}

.empty-text {
    font-size: 16px;
    font-weight: 500;
    margin: 0 0 8px 0;
}

.empty-hint {
    font-size: 13px;
    opacity: 0.6;
    margin: 0;
}

.chart-content {
    display: flex;
    gap: 20px;
    align-items: center;
    flex-direction: column;
}

.chart-wrapper {
    width: 200px;
    height: 200px;
    flex-shrink: 0;
}

.chart {
    width: 100%;
    height: 100%;
}

.chart-segment {
    transition: all 0.2s ease;
    cursor: pointer;
    opacity: 0.9;
}

.chart-segment:hover,
.chart-segment.highlighted {
    opacity: 1;
    filter: brightness(1.15);
}

/* ИСПРАВЛЕНО: правильное позиционирование текста */
.center-total {
    fill: var(--text-color);
    font-size: 9px;
    font-weight: 700;
    dominant-baseline: middle;
    text-anchor: middle;
}

.center-label {
    fill: var(--text-color);
    font-size: 6px;
    opacity: 0.7;
    dominant-baseline: middle;
    text-anchor: middle;
}

.legend {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 10px;
    width: 100%;
}

.legend-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 6px 8px;
    border-radius: 6px;
    cursor: pointer;
    transition: var(--transition);
}

.legend-item:hover {
    background-color: var(--hover-bg);
}

.legend-color {
    width: 10px;
    height: 10px;
    border-radius: 2px;
    flex-shrink: 0;
}

.legend-label {
    flex: 1;
    font-size: 12px;
    color: var(--text-color);
    opacity: 0.9;
}

.legend-value {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-color);
    white-space: nowrap;
}
</style>