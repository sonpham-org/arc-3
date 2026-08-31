"""q605 Waystation Grammar -- compose grouped caravan glyphs through shifting relays."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SAND,GLYPH0,GLYPH1,GLYPH2,RELAY,SHIFT,HISTORY,CODE,BAD=3,0,10,11,12,14,6,7,13,15
LEVELS=[
 {"name":"First Group","seq":(1,2,3)},{"name":"Shifted Relay","seq":(2,1,3,4)},
 {"name":"Two Groups","seq":(1,1,3,2,2,3)},{"name":"Recent Transform","seq":(1,2,3,4,2,1,3)},
 {"name":"Repeated Grammar","seq":(1,1,3,1,1,3,4,2,2,3)},
 {"name":"Waystation Grammar","seq":(2,1,3,4,1,2,3,2,2,3)}]
def advance(s,a):
 buf,shift,groups,recent,code=s;buf=list(buf)
 if a in (1,2):buf.append(a-1)
 elif a==3:
  if len(buf)<2:return None
  left,right=buf[-2:];kind=(left+2*right+shift+int(len(recent)==2 and recent[0]==recent[1]))%3;buf=buf[:-2];groups=groups+(kind,);recent=(recent+(kind,))[-2:];shift=(shift+kind)%3
 elif a==4:shift=(shift+1)%3
 elif a==5:
  if not groups or buf:return None
  code=(sum((i+1)*v for i,v in enumerate(groups))+shift)%5
 return tuple(buf),shift,groups,recent,code
for x in LEVELS:
 s=((),0,(),(),None)
 for a in x["seq"]:s=advance(s,a);assert s is not None
 x["plan"]=x["seq"]+(5,)
def target(x):
 s=((),0,(),(),None)
 for a in x["plan"]:s=advance(s,a);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=SAND;cols=(GLYPH0,GLYPH1,GLYPH2)
  for i in range(6):x=8+i*9;f[9:14,x:x+6]=cols[(i+g.shift)%3];f[18:21,x:x+7]=RELAY
  for i,v in enumerate(g.buf[-6:]):x=8+i*9;f[27:38,x:x+7]=cols[v]
  for i,v in enumerate(g.groups[-5:]):f[43:48,8+i*10:15+i*10]=cols[v]
  f[52:56,8:8+g.shift*15+9]=SHIFT
  if g.code is not None:f[54:59,43:56]=CODE
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q605(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q605",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.buf=();self.shift=0;self.groups=self.recent=();self.code=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.buf,self.shift,self.groups,self.recent,self.code),a)
   if s is None:self.bad=True;self.lose()
   else:self.buf,self.shift,self.groups,self.recent,self.code=s
  elif a==6:
   if (self.buf,self.shift,self.groups,self.recent,self.code)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
