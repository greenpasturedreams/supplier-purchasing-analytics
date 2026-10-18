"""EDA from executed SQL outputs. Elapsed time is calendar time, never labor time."""
from pathlib import Path
import os
ROOT=Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.mplconfig'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import numpy as np
import pandas as pd

DATA=ROOT/'data'/'processed'
OUT=ROOT/'reports'/'figures'
BLUE='#167D9A'; GOLD='#CB8A28'; PURPLE='#7657A4'; GREY='#64748B'


def save(fig,name,note=''):
    fig.text(.01,.012,'Source: BPI Challenge 2019 · van Dongen / 4TU.ResearchData · CC BY 4.0',fontsize=8,color=GREY)
    if note:
        fig.text(.01,.044,note,fontsize=8,color=GREY)
    fig.tight_layout(rect=[0,.085,1,.96])
    fig.savefig(OUT/name,dpi=160,facecolor='white')
    plt.close(fig)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,
        'axes.spines.right':False,'axes.titleweight':'bold','axes.grid':True,'grid.alpha':.15})
    cases=pd.read_csv(DATA/'analysis_cases.csv.gz')
    lead=cases.loc[cases.receipt_observed_90d==1,'first_receipt_days']
    stat=pd.read_csv(DATA/'metric_stats.csv')
    overall=stat.loc[stat.scope=='overall'].iloc[0]
    fig,ax=plt.subplots(figsize=(10.5,5.8))
    ax.hist(lead,bins=np.arange(0,92,2),color=BLUE,edgecolor='white',linewidth=.5)
    for value,label,color in [(overall.median_days,'Median',GOLD),(overall.p90_days,'P90',PURPLE)]:
        ax.axvline(value,color=color,lw=2,ls='--',label=f'{label}: {value:.1f} days')
    ax.set_title('How long until the first recorded goods receipt?',pad=18)
    ax.set_xlabel('Calendar days from purchase-order item creation');ax.set_ylabel('Purchase-order items')
    ax.legend()
    save(fig,'01_receipt_time_distribution.png',
        f'{len(lead):,} of {len(cases):,} eligible items ({cases.receipt_observed_90d.mean():.1%}) have a receipt within 90 days. Distribution excludes the rest.')

    suppliers=pd.read_csv(DATA/'analysis_02.csv')
    top=suppliers.head(12).sort_values('p90_p10_spread_days')
    fig,ax=plt.subplots(figsize=(11.5,7))
    y=np.arange(len(top))
    ax.hlines(y,top.p10_days,top.p90_days,color=BLUE,lw=4,alpha=.65,label='P10–P90 range')
    ax.scatter(top.median_days,y,color=GOLD,s=50,zorder=3,label='Median')
    labels=[f'{r.vendor_id}  |  n={r.eligible_cases:,}; receipt={r.receipt_share_90d:.0%}' for r in top.itertuples()]
    ax.set_yticks(y,labels,fontsize=9);ax.set_xlabel('Calendar days to first recorded receipt')
    ax.set_title('Wide supplier receipt-time ranges warrant closer review',pad=45)
    ax.legend(loc='lower left',bbox_to_anchor=(0,1.01),ncol=2,frameon=False)
    save(fig,'02_supplier_variability.png','12 widest ranges among suppliers with ≥50 eligible items and ≥30 observed receipts; observed receipts only; mix differs.')

    areas=pd.read_csv(DATA/'analysis_03.csv').query('eligible_cases >= 30').sort_values('median_days')
    fig,axes=plt.subplots(1,2,figsize=(12,6.2),sharey=True,gridspec_kw={'width_ratios':[2,1]})
    y=np.arange(len(areas))
    axes[0].barh(y,areas.median_days,color=BLUE,label='Median')
    axes[0].scatter(areas.p90_days,y,color=GOLD,s=35,label='P90',zorder=3)
    axes[0].set_yticks(y,[f'{r.spend_area} (n={r.eligible_cases:,})' for r in areas.itertuples()],fontsize=9)
    axes[0].set_xlabel('Calendar days to first receipt');axes[0].legend(loc='lower right')
    axes[1].barh(y,areas.receipt_share_90d,color=PURPLE)
    axes[1].set_xlim(0,1);axes[1].xaxis.set_major_formatter(PercentFormatter(1));axes[1].set_xlabel('Receipt observed within 90 days')
    fig.suptitle('Compare material families before judging suppliers',fontweight='bold',fontsize=15)
    save(fig,'03_material_family_comparison.png','Families with ≥30 eligible items; time percentiles use observed receipts, while coverage includes all eligible items in each family.')

    months=pd.read_csv(DATA/'analysis_04.csv')
    fig,axes=plt.subplots(2,1,figsize=(10.5,6.5),sharex=True)
    axes[0].plot(months.month,months.median_days,color=BLUE,marker='o',label='Median')
    axes[0].plot(months.month,months.p90_days,color=GOLD,marker='o',label='P90')
    axes[0].set_ylabel('Calendar days to first receipt');axes[0].legend(ncol=2,loc='center right')
    axes[1].bar(months.month,months.receipt_share_90d,color=PURPLE)
    axes[1].yaxis.set_major_formatter(PercentFormatter(1));axes[1].set_ylim(0,1)
    axes[1].set_ylabel('Receipt observed by day 90');axes[1].set_xlabel('PO item creation month (2018)')
    fig.suptitle('Monthly creation cohorts use the same observation window',fontweight='bold',fontsize=15)
    save(fig,'04_monthly_cohorts.png','January–September creations, each followed for 90 days; percentiles include only observed receipts, not unresolved items.')

    stages=pd.read_csv(DATA/'analysis_05.csv').sort_values('median_days')
    names={'PO creation to first receipt':'PO creation → first goods receipt',
        'PO creation to first confirmation':'PO creation → first confirmation',
        'First receipt to first invoice record':'First receipt → first invoice record',
        'First invoice record to first clearing':'First invoice record → first clearing'}
    fig,ax=plt.subplots(figsize=(11,5.8));y=np.arange(len(stages))
    ax.barh(y,stages.median_days,color=BLUE,label='Median')
    ax.scatter(stages.p90_days,y,color=GOLD,s=45,label='P90',zorder=3)
    ax.set_yticks(y,[f'{names[r.group_key]}\n(n={r.observations:,})' for r in stages.itertuples()],fontsize=9)
    ax.set_xlabel('Observed calendar days');ax.legend(loc='center right');ax.set_title('Recorded milestones reveal where elapsed time accumulates',pad=16)
    save(fig,'05_purchasing_stage_intervals.png','Different eligible populations; stages do not add to a single total. Invoice and clearing records are not transaction-matched.')

    context=suppliers.loc[suppliers.benchmarked_cases>=50].nlargest(15,'eligible_cases').sort_values('difference_pp')
    fig,ax=plt.subplots(figsize=(11,6.5));y=np.arange(len(context))
    ax.barh(y,context.difference_pp,color=[BLUE if v>=0 else GOLD for v in context.difference_pp])
    ax.set_yticks(y,[f'{r.vendor_id} (benchmarked n={int(r.benchmarked_cases):,})' for r in context.itertuples()],fontsize=9)
    ax.axvline(0,color=GREY,lw=1);ax.set_xlabel('Receipt-by-day-90 share minus mix benchmark (percentage points)')
    ax.set_title('Supplier coverage in the context of purchasing mix',pad=16)
    save(fig,'06_supplier_mix_context.png','15 largest qualified suppliers; benchmark = company × material subcategory × matching process, ≥30 items/stratum; focal supplier included.')

    transitions=pd.read_csv(DATA/'analysis_06.csv').head(8).iloc[::-1]
    fig,ax=plt.subplots(figsize=(12,7))
    y=np.arange(len(transitions));ax.barh(y,transitions.total_case_days/1000,color=BLUE)
    ax.set_yticks(y,[f'{r.from_activity}\n→ {r.to_activity}' for r in transitions.itertuples()],fontsize=9)
    ax.set_xlabel('Summed elapsed time across PO items (thousands of case-days)')
    ax.set_title('Frequent long intervals identify process steps to investigate',pad=16)
    save(fig,'07_event_interval_bottlenecks.png','Adjacent events within each item’s 90-day window; ≥100 intervals/type. Calendar time is not labor, plant downtime, or recoverable savings.')

    patterns=pd.read_csv(DATA/'analysis_08.csv')
    fig,axes=plt.subplots(1,2,figsize=(11,5.8))
    labels={'No receipt by day 90':'No receipt\nby day 90','One receipt posting':'One receipt\nposting','Multiple receipt postings':'Multiple receipt\npostings'}
    axes[0].bar([labels[x] for x in patterns.receipt_pattern],patterns.cases,color=[BLUE,GOLD,PURPLE])
    axes[0].set_ylabel('Eligible PO items');axes[0].set_title('Receipt posting patterns',fontsize=12)
    spans=cases.loc[cases.gr_records_90d>1,'receipt_span_days']
    axes[1].hist(spans,bins=np.linspace(0,90,31),color=BLUE,edgecolor='white')
    axes[1].set_xlabel('Days between first and last receipt posting');axes[1].set_ylabel('Items with repeated postings')
    axes[1].set_title('Observed receipt-posting span',fontsize=12)
    fig.suptitle('A first receipt is not proof of complete delivery',fontweight='bold',fontsize=15)
    save(fig,'08_repeated_receipt_postings.png','Repeated records can include separate deliveries, recurring postings, or identical content; no quantities or posting IDs establish full completion.')
    print('Saved eight EDA figures')


if __name__=='__main__':
    main()
