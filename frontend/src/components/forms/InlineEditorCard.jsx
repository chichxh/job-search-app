import { useMemo, useState } from 'react';

export default function InlineEditorCard({
  title,
  summary,
  value,
  renderFields,
  onSave,
  onDelete,
  disabled = false,
}) {
  const [isEditing, setIsEditing] = useState(!value?.id);
  const [draft, setDraft] = useState(value);

  const canDelete = useMemo(() => Boolean(onDelete && value?.id), [onDelete, value?.id]);

  function startEditing() {
    setDraft(value);
    setIsEditing(true);
  }

  function cancelEditing() {
    setDraft(value);
    setIsEditing(false);
  }

  async function handleSave() {
    await onSave(draft);
    setIsEditing(false);
  }

  return (
    <article className="editor-card">
      <header className="editor-card__header">
        <strong>{title}</strong>
        {!isEditing ? (
          <button type="button" className="button button--ghost" onClick={startEditing} disabled={disabled}>
            Редактировать
          </button>
        ) : null}
      </header>

      {!isEditing ? <p className="editor-card__summary">{summary}</p> : null}

      {isEditing ? (
        <div className="editor-card__form">
          {renderFields(draft, setDraft)}
          <div className="editor-card__actions">
            <button type="button" className="button" onClick={handleSave} disabled={disabled}>
              {disabled ? 'Сохранение...' : 'Сохранить'}
            </button>
            <button type="button" className="button button--ghost" onClick={cancelEditing} disabled={disabled}>
              Отмена
            </button>
            {canDelete ? (
              <button type="button" className="button button--danger" onClick={() => onDelete(value.id)} disabled={disabled}>
                Удалить
              </button>
            ) : null}
          </div>
        </div>
      ) : null}
    </article>
  );
}
