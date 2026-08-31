"""a086 Counterbrace -- pair one-way braces against alternating sway."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,SKY,TOWER,BRACE_L,BRACE_R,WIND,LOAD,SAFE,SWAY,BAD=14,8,9,12,10,11,13,6,4,15
LEVELS=[
 {"name":"Place Left Brace","seq":(1,)},{"name":"Select Bay","seq":(2,)},
 {"name":"Reverse Wind","seq":(3,1)},{"name":"Pair Diagonals","seq":(1,2,1,3,4)},
 {"name":"Alternating Load","seq":(1,2,1,3,4,3,4)},{"name":"Counterbrace","seq":(1,2,1,3,4,2,1,3,4,3)},
]
def advance(s,a):
 braces,cursor,wind,sway,safe,history,snapshot=s;b=list(braces)
 if a==1:b[cursor]=0 if b[cursor]==1 else b[cursor]+1;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%4;history=(history+(2,))[-8:]
 elif a==3:wind*=-1;history=(history+(3,))[-8:]
 elif a==4:
  resistance=sum(int(x==wind) for x in b);sway=max(-4,min(4,sway+wind*(2-resistance)));safe=min(5,safe+1) if abs(sway)<=1 and resistance else 0;wind*=-1;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(b),cursor,wind,sway,safe,history)
 return tuple(b),cursor,wind,sway,safe,history,snapshot
for x in LEVELS:
 s=((0,0,0,0),0,-1,0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=SKY;shift=g.sway*2;f[10:55,27+shift:38+shift]=TOWER
  for i,d in enumerate(g.braces):
   y1=51-i*10;y2=y1-9
   if d:
    x1=18 if d<0 else 47;x2=31+shift
    for j in range(10):x=x1+(x2-x1)*j//9;y=y1+(y2-y1)*j//9;f[y:y+3,x:x+3]=BRACE_L if d<0 else BRACE_R
   if i==g.cursor:f[y2:y2+3,8:18]=LOAD
  f[7:12,8:23]=WIND;f[7:12,24:24+(8 if g.wind>0 else 3)]=LOAD
  for i in range(g.safe):f[55:58,8+i*8:14+i*8]=SAFE
  if g.bad:f[1:4,18:46]=BAD
  return f
class A086(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a086",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.braces,self.cursor,self.wind,self.sway,self.safe,self.history,self.snapshot=((0,0,0,0),0,-1,0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.braces,self.cursor,self.wind,self.sway,self.safe,self.history,self.snapshot=advance((self.braces,self.cursor,self.wind,self.sway,self.safe,self.history,self.snapshot),a)
  elif a==6:
   if (self.braces,self.cursor,self.wind,self.sway,self.safe,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
