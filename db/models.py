from sqlalchemy import Column, Integer, Text, TIMESTAMP, ForeignKey, \
    UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship
import datetime

Base = declarative_base()


class Channel(Base):
    __tablename__ = 'channels_to_listen'
    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, nullable=False)
    title = Column(Text, nullable=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)


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


class TargetChannel(Base):
    __tablename__ = 'target_channels'
    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, nullable=False)
    title = Column(Text, nullable=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    rewrite_prompt = Column(Text, nullable=True)

    tags = relationship(
        "TargetChannelTag",
        backref="target_channel",
        cascade="all, delete-orphan"
    )


class TargetChannelTag(Base):
    __tablename__ = 'target_channel_tags'
    id = Column(Integer, primary_key=True)
    target_channel_id = Column(Integer, ForeignKey('target_channels.id'),
                               nullable=False)
    tag_id = Column(Integer, ForeignKey('tags.id'), nullable=False)

    __table_args__ = (UniqueConstraint('target_channel_id', 'tag_id',
                                       name='_target_channel_tag_uc'),)


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
