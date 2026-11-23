import { cn } from "@/lib/utils";

export interface SeriesDef {
	key: string;
	label: string;
	color: string;
}

type Point = { label: string } & Record<string, number | string>;

const VIEW_WIDTH = 760;

/**
 * Dependency-free responsive line chart. Renders as inline SVG so it works
 * during SSR and needs no charting library.
 */
export function TrendChart({
	data,
	series,
	height = 240,
	className,
}: {
	data: Point[];
	series: SeriesDef[];
	height?: number;
	className?: string;
}) {
	const padding = { top: 16, right: 18, bottom: 30, left: 40 };
	const innerWidth = VIEW_WIDTH - padding.left - padding.right;
	const innerHeight = height - padding.top - padding.bottom;

	const max = Math.max(
		1,
		...data.flatMap((point) =>
			series.map((definition) => Number(point[definition.key]) || 0),
		),
	);

	const xFor = (index: number) =>
		padding.left +
		(data.length <= 1
			? innerWidth / 2
			: (index / (data.length - 1)) * innerWidth);
	const yFor = (value: number) =>
		padding.top + innerHeight - (value / max) * innerHeight;

	const gridLines = [0, 0.25, 0.5, 0.75, 1];
	const labelStep = Math.max(1, Math.ceil(data.length / 7));

	return (
		<div className={cn("w-full", className)}>
			<svg
				viewBox={`0 0 ${VIEW_WIDTH} ${height}`}
				className="h-auto w-full"
				role="img"
				aria-label="Trend chart"
			>
				{gridLines.map((ratio) => {
					const y = padding.top + innerHeight * ratio;
					const value = Math.round(max * (1 - ratio));
					return (
						<g key={ratio}>
							<line
								x1={padding.left}
								x2={VIEW_WIDTH - padding.right}
								y1={y}
								y2={y}
								stroke="#f1f5f9"
								strokeWidth={1}
							/>
							<text
								x={padding.left - 8}
								y={y + 3}
								textAnchor="end"
								className="fill-zinc-400"
								fontSize={10}
							>
								{value}
							</text>
						</g>
					);
				})}

				{series.map((definition) => {
					const path = data
						.map((point, index) => {
							const value = Number(point[definition.key]) || 0;
							return `${index === 0 ? "M" : "L"} ${xFor(index).toFixed(1)} ${yFor(value).toFixed(1)}`;
						})
						.join(" ");
					return (
						<path
							key={definition.key}
							d={path}
							fill="none"
							stroke={definition.color}
							strokeWidth={2}
							strokeLinejoin="round"
							strokeLinecap="round"
						/>
					);
				})}

				{series.map((definition) =>
					data.map((point, index) => {
						const value = Number(point[definition.key]) || 0;
						if (value === 0) return null;
						return (
							<circle
								key={`${definition.key}-${point.label}`}
								cx={xFor(index)}
								cy={yFor(value)}
								r={2.2}
								fill={definition.color}
							/>
						);
					}),
				)}

				{data.map((point, index) =>
					index % labelStep === 0 ? (
						<text
							key={point.label}
							x={xFor(index)}
							y={height - 10}
							textAnchor="middle"
							className="fill-zinc-400"
							fontSize={10}
						>
							{point.label}
						</text>
					) : null,
				)}
			</svg>

			<div className="mt-2 flex flex-wrap items-center gap-4">
				{series.map((definition) => (
					<span
						key={definition.key}
						className="inline-flex items-center gap-1.5 text-xs text-zinc-600"
					>
						<span
							className="size-2.5 rounded-full"
							style={{ backgroundColor: definition.color }}
						/>
						{definition.label}
					</span>
				))}
			</div>
		</div>
	);
}

/** Horizontal bar breakdown, e.g. actions by type. */
export function BarBreakdown({
	data,
}: {
	data: Array<{ label: string; value: number; color: string }>;
}) {
	const max = Math.max(1, ...data.map((entry) => entry.value));
	return (
		<div className="space-y-3">
			{data.map((entry) => (
				<div key={entry.label}>
					<div className="mb-1 flex items-center justify-between text-xs">
						<span className="font-medium text-zinc-700">{entry.label}</span>
						<span className="text-zinc-500">{entry.value}</span>
					</div>
					<div className="h-2 overflow-hidden rounded-full bg-zinc-100">
						<div
							className="h-full rounded-full"
							style={{
								width: `${Math.max(2, (entry.value / max) * 100)}%`,
								backgroundColor: entry.color,
							}}
						/>
					</div>
				</div>
			))}
			{data.length === 0 ? (
				<p className="text-xs text-zinc-400">No activity recorded yet.</p>
			) : null}
		</div>
	);
}

/** Tiny inline trend line for stat cards. */
export function Sparkline({
	values,
	color = "#4f46e5",
	className,
}: {
	values: number[];
	color?: string;
	className?: string;
}) {
	const width = 120;
	const height = 32;
	const max = Math.max(1, ...values);
	const points = values.map((value, index) => {
		const x =
			values.length <= 1 ? width / 2 : (index / (values.length - 1)) * width;
		const y = height - (value / max) * height;
		return `${index === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
	});
	return (
		<svg
			viewBox={`0 0 ${width} ${height}`}
			className={cn("h-8 w-28", className)}
			aria-hidden="true"
		>
			<path
				d={points.join(" ")}
				fill="none"
				stroke={color}
				strokeWidth={2}
				strokeLinecap="round"
				strokeLinejoin="round"
			/>
		</svg>
	);
}
