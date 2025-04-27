from sqlalchemy import Column, Integer, Text, TIMESTAMP, ForeignKey
from sqlalchemy.orm import declarative_base
import datetime

Base = declarative_base()

class Channel(Base):
    __tablename__ = 'channels_to_listen'
    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, unique=True, nullable=False)
    title = Column(Text, nullable=True)


class ParsedPost(Base):
    __tablename__ = 'parsed_posts'
    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, nullable=False)
    chat_id = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    ts = Column(TIMESTAMP, default=datetime.datetime.utcnow)

class Tag(Base):
    __tablename__ = 'tags'
    id = Column(Integer, primary_key=True)
    name = Column(Text, unique=True, nullable=False)

class PostTag(Base):
    __tablename__ = 'post_tags'
    id = Column(Integer, primary_key=True)
    post_id = Column(Integer, ForeignKey('parsed_posts.id'), nullable=False)
    tag_id = Column(Integer, ForeignKey('tags.id'), nullable=False)