<?php
declare(strict_types=1);

function workflow_progress_markup(string $type,string $status,string $title,string $reference='',string $updatedAt='',string $note='',string $href=''): string {
    $flows=[
        'motion'=>['Submitted','Hansard review','Speaker review','Correction requested','Resubmitted to Hansard','Approved for tabling'],
        'petition'=>['Submitted','Hansard review','Speaker review','Correction requested','Resubmitted to Hansard','Converted to motion'],
        'voting'=>['Submitted','Speaker approval','Correction requested','MCA voting','Hansard result review','Speaker result approval'],
        'sitting'=>['Scheduled','Speaker approval','Correction requested','Resubmitted','Approved','Attendance recording','Attendance approved'],
        'attendance'=>['Recorded by Hansard','Speaker review','Approved for MCA'],
        'committee'=>['Prepared','Speaker review','Correction requested','Resubmitted','Approved'],
        'report'=>['Prepared','Speaker approval','Approved for download'],
    ];
    $positions=[
        'motion'=>['hansard_review'=>1,'speaker_review'=>2,'approved_for_tabling'=>6,'returned_for_correction'=>3],
        'petition'=>['hansard_review'=>1,'speaker_review'=>2,'approved'=>6,'returned_for_correction'=>3],
        'voting'=>['speaker_review'=>1,'returned_for_correction'=>2,'open'=>3,'hansard_result_review'=>4,'result_returned'=>4,'result_pending'=>5,'result_approved'=>6],
        'sitting'=>['speaker_review'=>1,'returned_for_correction'=>2,'approved'=>5,'completed'=>7],
        'attendance'=>['not_submitted'=>0,'speaker_review'=>1,'approved'=>3],
        'committee'=>['speaker_review'=>1,'returned_for_correction'=>2,'approved'=>5],
        'report'=>['speaker_review'=>1,'approved'=>3],
    ];
    $steps=$flows[$type]??['Submitted','Review','Completed'];
    $current=$positions[$type][$status]??0;
    $returned=in_array($status,['returned_for_correction','result_returned'],true);
    $stateText=$returned?'Returned for correction':status_label($status);
    $tag=$reference!==''?'<span class="record-ref">'.h($reference).'</span>':'';
    $titleHtml=$href!==''?'<a href="'.h($href).'">'.h($title).'</a>':h($title);
    $out='<article class="progress-card'.($returned?' is-returned':'').'">'
        .'<div class="progress-card-header"><div>'.$tag.'<h3>'.$titleHtml.'</h3></div><span class="badge '.h($status).'">'.h($stateText).'</span></div>'
        .'<ol class="progress-steps" aria-label="Workflow progress for '.h($title).'">';
    foreach($steps as $index=>$label){
        $class=$index<$current?'is-complete':($index===$current?'is-current':'is-upcoming');
        $aria=$index===$current?' aria-current="step"':'';
        $out.='<li class="progress-step '.$class.'"'.$aria.'><span class="progress-node" aria-hidden="true">'.($index<$current?'✓':(string)($index+1)).'</span><span class="progress-label">'.h($label).'</span></li>';
    }
    $out.='</ol>';
    if($returned&&$note!=='')$out.='<p class="progress-note"><strong>Correction requested:</strong> '.h($note).'</p>';
    if($updatedAt!=='')$out.='<small class="progress-updated">Last updated '.h(substr($updatedAt,0,16)).'</small>';
    return $out.'</article>';
}
