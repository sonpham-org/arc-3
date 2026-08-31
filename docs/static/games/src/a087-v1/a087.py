"""a087 Archipelago Bridge -- sequence spans and shims around settlement."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,SEA,ISLAND,PIER,SPAN,SHIM,SETTLE,LEVEL,CURSOR,BAD=15,8,9,4,12,14,10,13,6,11
LEVELS=[
 {"name":"Place Span","seq":(1,)},{"name":"Add Shim","seq":(2,)},
 {"name":"Select Pier","seq":(3,1,2)},{"name":"Settle Load","seq":(1,4,3,2,1)},
 {"name":"Sequence Spans","seq":(1,3,1,4,2,3,2)},{"name":"Archipelago Bridge","seq":(1,4,3,2,1,3,4,2,1,4)},
]
def advance(s,a):
 heights,spans,shims,cursor,settlement,history,snapshot=s;h=list(heights);sp=list(spans);sh=list(shims);st=list(settlement)
 if a==1:
  i=min(2,cursor);sp[i]=1;h[i]=max(1,h[i]-1);h[i+1]=max(1,h[i+1]-1);st[i]+=1;st[i+1]+=1;history=(history+(1,))[-8:]
 elif a==2:sh[cursor]=min(3,sh[cursor]+1);h[cursor]+=1;history=(history+(2,))[-8:]
 elif a==3:cursor=(cursor+1)%4;history=(history+(3,))[-8:]
 elif a==4:
  for i in range(4):
   load=int((i>0 and sp[i-1]) or (i<3 and sp[i]));h[i]=max(1,h[i]-load);st[i]+=load
  history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(h),tuple(sp),tuple(sh),cursor,tuple(st),history)
 return tuple(h),tuple(sp),tuple(sh),cursor,tuple(st),history,snapshot
for x in LEVELS:
 s=((5,4,6,3),(0,0,0),(0,0,0,0),0,(0,0,0,0),(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=SEA
  xs=(8,23,38,53)
  for i,(x,h) in enumerate(zip(xs,g.heights)):
   f[48:57,x-5:x+6]=ISLAND;top=47-h*4;f[top:48,x-2:x+3]=PIER
   for j in range(g.shims[i]):f[top-j*2-2:top-j*2,x-4:x+5]=SHIM
   if i==g.cursor:f[55:59,x-5:x+6]=CURSOR
  for i,on in enumerate(g.spans):
   if on:y=min(47-g.heights[i]*4,47-g.heights[i+1]*4);f[y-3:y+1,xs[i]:xs[i+1]+1]=SPAN
  for i,v in enumerate(g.settlement):f[7+i*4:10+i*4,8:8+v*4]=SETTLE
  f[7:11,43:57]=LEVEL
  if g.bad:f[1:4,18:46]=BAD
  return f
class A087(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a087",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.heights,self.spans,self.shims,self.cursor,self.settlement,self.history,self.snapshot=((5,4,6,3),(0,0,0),(0,0,0,0),0,(0,0,0,0),(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.heights,self.spans,self.shims,self.cursor,self.settlement,self.history,self.snapshot=advance((self.heights,self.spans,self.shims,self.cursor,self.settlement,self.history,self.snapshot),a)
  elif a==6:
   if (self.heights,self.spans,self.shims,self.cursor,self.settlement,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
