"""q608 Asterism Grammar -- compose grouped star glyphs through precessing relays."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,GLYPH0,GLYPH1,GLYPH2,RELAY,PHASE,CODE,GOAL,BAD=3,4,10,11,12,14,6,9,13,15
LEVELS=[
 {"name":"Paired Glyphs","seq":(1,2)},{"name":"First Relay","seq":(1,2,3)},
 {"name":"Grouped Turn","seq":(2,1,2,4)},{"name":"Precessed Message","seq":(1,2,3,1,4)},
 {"name":"Nested Relay","seq":(2,1,3,2,4,3)},{"name":"Asterism Grammar","seq":(1,2,2,3,1,4,2,3,4)}]
def advance(s,a):
 buf,phase,relays,code=s;buf=list(buf)
 if a in (1,2):buf.append(a-1)
 elif a==3:
  buf=[(v+phase+1)%3 for v in reversed(buf)];phase=(phase+1)%3
 elif a==4:
  if buf:buf=buf[1:]+buf[:1]
  relays+=1
 elif a==5:
  if len(buf)<2:return None
  code=(sum((i+1)*v for i,v in enumerate(buf))+phase+relays)%5
 return tuple(buf),phase,relays,code
for x in LEVELS:
 s=((),0,0,None)
 for a in x["seq"]:s=advance(s,a);assert s is not None
 x["plan"]=x["seq"]+(5,)
def target(x):
 s=((),0,0,None)
 for a in x["plan"]:s=advance(s,a);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FIELD
  cols=(GLYPH0,GLYPH1,GLYPH2)
  for i in range(6):
   x=8+i*9;f[9:14,x:x+5]=cols[(i+g.phase)%3];f[18:21,x:x+7]=RELAY
  for i,v in enumerate(g.buf[-6:]):x=8+i*9;f[29:42,x:x+7]=cols[v]
  f[47:51,8:8+g.phase*14+8]=PHASE
  f[53:57,8:8+min(g.relays,5)*9]=RELAY
  if g.code is not None:f[52:59,45:56]=CODE if g.code%2 else GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q608(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q608",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.buf=();self.phase=self.relays=0;self.code=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.buf,self.phase,self.relays,self.code),a)
   if s is None:self.bad=True;self.lose()
   else:self.buf,self.phase,self.relays,self.code=s
  elif a==6:
   if (self.buf,self.phase,self.relays,self.code)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
