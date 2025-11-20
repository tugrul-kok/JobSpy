from flask import Flask, render_template, request, jsonify, send_file, session
from jobspy import scrape_jobs
import pandas as pd
import io
import uuid
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'

# Store results temporarily (in production, consider using Redis or database)
results_cache = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search_jobs():
    try:
        # Get form data
        site_name = request.form.get('site_name')
        search_term = request.form.get('search_term')
        location = request.form.get('location', '')
        results_wanted = int(request.form.get('results_wanted', 50))
        hours_old = request.form.get('hours_old')
        hours_old = int(hours_old) if hours_old else None
        
        # Validate required fields
        if not site_name or not search_term:
            return jsonify({'error': 'Site name and search term are required'}), 400
        
        print(f"Searching for: {search_term} on {site_name}")
        
        # Perform job search
        jobs = scrape_jobs(
            site_name=[site_name],
            search_term=search_term,
            location=location if location else None,
            results_wanted=results_wanted,
            hours_old=hours_old,
            country_indeed='Netherlands',  # You can make this configurable too
        )
        
        # Generate unique ID for this search result
        result_id = str(uuid.uuid4())
        
        # Store results in cache
        results_cache[result_id] = {
            'jobs': jobs,
            'search_params': {
                'site_name': site_name,
                'search_term': search_term,
                'location': location,
                'results_wanted': results_wanted,
                'hours_old': hours_old,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        }
        
        # Convert DataFrame to HTML table
        if len(jobs) > 0:
            # Select key columns for display
            display_columns = ['title', 'company', 'location', 'job_type', 'date_posted', 'job_url', 'site']
            available_columns = [col for col in display_columns if col in jobs.columns]
            jobs_display = jobs[available_columns].copy()  # Use .copy() to avoid SettingWithCopyWarning
            
            # Make job URLs clickable
            if 'job_url' in jobs_display.columns:
                jobs_display.loc[:, 'job_url'] = jobs_display['job_url'].apply(
                    lambda x: f'<a href="{x}" target="_blank">View Job</a>' if pd.notna(x) else ''
                )
            
            table_html = jobs_display.to_html(
                classes='table table-striped table-hover',
                table_id='jobsTable',
                escape=False,
                index=False
            )
        else:
            table_html = '<p class="text-muted">No jobs found for your search criteria.</p>'
        
        return jsonify({
            'success': True,
            'table_html': table_html,
            'job_count': len(jobs),
            'result_id': result_id
        })
        
    except Exception as e:
        print(f"Error during job search: {str(e)}")
        return jsonify({'error': f'Search failed: {str(e)}'}), 500

@app.route('/download/<result_id>/<format>')
def download_results(result_id, format):
    try:
        if result_id not in results_cache:
            return "Results not found or expired", 404
        
        jobs = results_cache[result_id]['jobs']
        search_params = results_cache[result_id]['search_params']
        
        # Create filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"jobs_{search_params['search_term'].replace(' ', '_')}_{timestamp}"
        
        if format == 'csv':
            # Create CSV
            output = io.StringIO()
            jobs.to_csv(output, index=False)
            output.seek(0)
            
            # Convert to bytes
            csv_data = io.BytesIO()
            csv_data.write(output.getvalue().encode('utf-8'))
            csv_data.seek(0)
            
            return send_file(
                csv_data,
                mimetype='text/csv',
                as_attachment=True,
                download_name=f'{filename}.csv'
            )
            
        elif format == 'excel':
            # Create Excel file
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                jobs.to_excel(writer, sheet_name='Jobs', index=False)
                
                # Add search parameters as a separate sheet
                params_df = pd.DataFrame([search_params])
                params_df.to_excel(writer, sheet_name='Search_Parameters', index=False)
            
            output.seek(0)
            
            return send_file(
                output,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=f'{filename}.xlsx'
            )
        
        else:
            return "Invalid format", 400
            
    except Exception as e:
        print(f"Error during download: {str(e)}")
        return f"Download failed: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)
