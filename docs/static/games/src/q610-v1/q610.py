"""q610 Vault Grammar -- compose a message while two echo ledgers move independently."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,VAULT,GLYPH0,GLYPH1,GROUP,A_ECHO,B_ECHO,COMMIT,BAD=3,11,9,14,10,12,6,13,15
LEVELS=[
 {"name":"Two Glyphs","glyphs":(1,2),"reverse":0},{"name":"Grouped Echo","glyphs":(2,1,2),"reverse":0},
 {"name":"Reversed Passage","glyphs":(1,2,2),"reverse":1},{"name":"Dual Grammar","glyphs":(2,1,1,2),"reverse":0},
 {"name":"Long Relation","glyphs":(1,2,1,2,2),"reverse":1},{"name":"Vault Grammar","glyphs":(2,1,2,2,1,2),"reverse":1}]
def rotate(boxes,q):
 b=[list(v) for v in boxes];vals=[v[q] for v in b];vals=vals[-1:]+vals[:-1]
 for i,v in enumerate(vals):b[i][q]=v
 return tuple(map(tuple,b))
def decode(buf,boxes):return (sum((i+1)*v for i,v in enumerate(buf))+boxes[1][0]+2*boxes[1][1])%4
for x in LEVELS:
 boxes=((2,1),(0,1),(1,0));buf=[]
 for a in x["glyphs"]:buf.append(a-1);boxes=rotate(boxes,a-1)
 if x["reverse"]:buf.reverse();boxes=tuple(reversed(boxes))
 x["target"]=decode(buf,boxes);x["plan"]=x["glyphs"]+(3,)*x["reverse"]+(4,5)
def advance(s,a,x):
 boxes,buf,code,committed=s;buf=list(buf)
 if a in (1,2):buf.append(a-1);boxes=rotate(boxes,a-1)
 elif a==3:buf.reverse();boxes=tuple(reversed(boxes))
 elif a==4:
  if len(buf)<2:return None
  code=decode(buf,boxes)
 elif a==5:
  if code!=x["target"]:return None
  committed=(code,boxes)
 return boxes,tuple(buf),code,committed
def target(x):
 s=(((2,1),(0,1),(1,0)),(),None,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=VAULT;f[8:31,8:56]=GROUP
  for i,b in enumerate(g.buf[-6:]):x=10+i*7;f[12:27,x:x+5]=GLYPH1 if b else GLYPH0
  for i,(a,b) in enumerate(g.boxes):x=10+i*15;f[36:40,x:x+a*4]=A_ECHO;f[44:48,x:x+b*4]=B_ECHO
  if g.committed:f[54:59,39:56]=COMMIT
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q610(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q610",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.boxes=((2,1),(0,1),(1,0));self.buf=();self.code=self.committed=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.boxes,self.buf,self.code,self.committed),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.boxes,self.buf,self.code,self.committed=s
  elif a==6:
   if (self.boxes,self.buf,self.code,self.committed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
