import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import styles from './AutoBeautify.module.css';

interface AutoBeautifyProps {
    content: string;
    className?: string;
}

export default function AutoBeautify({ content, className = '' }: AutoBeautifyProps) {
    return (
        <div className={`${styles.autoBeautify} ${className}`}>
            <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>
                {content}
            </ReactMarkdown>
        </div>
    );
}
